"""
=====================================================================================
 AGENT 1: DATA INGESTION & PREPROCESSING AGENT
=====================================================================================
Role
----
Takes raw, noisy, potentially huge tabular data and turns it into a clean,
numeric, scaled dataframe ready to be consumed by Agent 2 (Anomaly Detector).

Techniques used (all "gradient-boosting flavoured"):
  1. Chunked / memory-optimized ingestion for large CSVs.
  2. Automatic dtype downcasting (memory reduction).
  3. Out-of-fold K-Fold TARGET ENCODING for high-cardinality categoricals
     (leakage-safe mean-encoding, the same trick used in Kaggle-style
     gradient boosting pipelines).
  4. Tree-based ITERATIVE IMPUTATION (sklearn's IterativeImputer driven by an
     XGBRegressor estimator instead of the default BayesianRidge -> imputes
     missing values the way a boosted-tree model "sees" the data).
  5. XGBoost FEATURE-IMPORTANCE-BASED FEATURE SELECTION (drop noisy / low
     signal columns before they reach the anomaly detector).
  6. Power transform (Yeo-Johnson) + scaling to stabilize skewed numeric
     distributions -> improves LightGBM split quality downstream.

Author: ML Engineering reference implementation
=====================================================================================
"""

import gc
import warnings
from typing import List, Optional, Union

import numpy as np
import pandas as pd
import xgboost as xgb

from sklearn.experimental import enable_iterative_imputer  # noqa: F401 (required to unlock IterativeImputer)
from sklearn.impute import IterativeImputer, SimpleImputer
from sklearn.preprocessing import PowerTransformer, StandardScaler
from sklearn.model_selection import KFold

warnings.filterwarnings("ignore")


def _is_categorical_like(series: pd.Series) -> bool:
    """
    True for object / pandas-string / category dtype columns.
    Handles both classic pandas (<2.0) 'object' string columns and the
    newer pandas 'str' / StringDtype / ArrowDtype string representations.
    """
    dtype = series.dtype
    return (
        pd.api.types.is_object_dtype(dtype)
        or pd.api.types.is_string_dtype(dtype)
        or isinstance(dtype, pd.CategoricalDtype)
    )


class DataIngestionAgent:
    """
    Agent 1 — ingests raw data and produces a clean, scaled, model-ready dataframe.

    Parameters
    ----------
    chunksize : int
        Rows per chunk when reading large CSV files from disk.
    target_col : str, optional
        Name of a supervised target column (if present) used to drive
        target-encoding and importance-based feature selection. If None,
        those two steps are skipped automatically (fully unsupervised mode).
    importance_top_k : int, optional
        Keep only the top-k most important features according to XGBoost.
        Mutually usable with `importance_threshold`.
    importance_threshold : float, optional
        Alternative to top_k -- keep features whose normalized importance
        exceeds this threshold (e.g. 0.01).
    max_categorical_cardinality : int
        Categorical columns with cardinality above this are target-encoded;
        low-cardinality ones are one-hot encoded instead.
    random_state : int
        Reproducibility seed.
    """

    def __init__(
        self,
        chunksize: int = 50_000,
        target_col: Optional[str] = None,
        importance_top_k: Optional[int] = None,
        importance_threshold: Optional[float] = None,
        max_categorical_cardinality: int = 15,
        random_state: int = 42,
    ):
        self.chunksize = chunksize
        self.target_col = target_col
        self.importance_top_k = importance_top_k
        self.importance_threshold = importance_threshold
        self.max_categorical_cardinality = max_categorical_cardinality
        self.random_state = random_state

        # fitted state, populated during fit_transform
        self.numeric_cols_: List[str] = []
        self.categorical_cols_: List[str] = []
        self.target_encoding_maps_: dict = {}
        self.global_target_mean_: Optional[float] = None
        self.selected_features_: List[str] = []
        self.feature_importances_: Optional[pd.Series] = None
        self.imputer_: Optional[IterativeImputer] = None
        self.power_transformer_: Optional[PowerTransformer] = None
        self.scaler_: Optional[StandardScaler] = None

    # ------------------------------------------------------------------ #
    # 1. INGESTION
    # ------------------------------------------------------------------ #
    def load_data(self, source: Union[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Load data either from an in-memory DataFrame or from a (potentially
        huge) CSV file on disk, using chunked reads + per-chunk memory
        optimization to stay efficient on large datasets.
        """
        if isinstance(source, pd.DataFrame):
            return self.reduce_memory_usage(source.copy())

        print(f"[Agent1] Streaming CSV in chunks of {self.chunksize} rows ...")
        chunks = []
        for i, chunk in enumerate(pd.read_csv(source, chunksize=self.chunksize)):
            chunk = self.reduce_memory_usage(chunk)
            chunks.append(chunk)
            print(f"[Agent1]   chunk {i + 1} loaded -> {chunk.shape}")
        df = pd.concat(chunks, ignore_index=True)
        del chunks
        gc.collect()
        print(f"[Agent1] Full dataset assembled -> {df.shape}")
        return df

    @staticmethod
    def reduce_memory_usage(df: pd.DataFrame) -> pd.DataFrame:
        """Downcast numeric dtypes to the smallest safe type to save RAM."""
        start_mem = df.memory_usage(deep=True).sum() / 1024 ** 2
        for col in df.columns:
            col_type = df[col].dtype
            if pd.api.types.is_integer_dtype(col_type):
                df[col] = pd.to_numeric(df[col], downcast="integer")
            elif pd.api.types.is_float_dtype(col_type):
                df[col] = pd.to_numeric(df[col], downcast="float")
            elif _is_categorical_like(df[col]) and not isinstance(col_type, pd.CategoricalDtype):
                # Keep low-cardinality strings as 'category' to save memory
                num_unique = df[col].nunique(dropna=True)
                if num_unique / max(len(df), 1) < 0.5:
                    df[col] = df[col].astype("category")
        end_mem = df.memory_usage(deep=True).sum() / 1024 ** 2
        if start_mem > 0:
            print(f"[Agent1]   memory reduced: {start_mem:.2f}MB -> {end_mem:.2f}MB "
                  f"({100 * (start_mem - end_mem) / start_mem:.1f}% saved)")
        return df

    # ------------------------------------------------------------------ #
    # 2. CATEGORICAL ENCODING (K-Fold Target Encoding, leakage-safe)
    # ------------------------------------------------------------------ #
    def encode_categoricals(self, df: pd.DataFrame, n_splits: int = 5) -> pd.DataFrame:
        cat_cols = [c for c in df.columns
                    if _is_categorical_like(df[c]) and c != self.target_col]
        self.categorical_cols_ = cat_cols

        if not cat_cols:
            return df

        if self.target_col is None or self.target_col not in df.columns:
            # Unsupervised fallback: simple frequency/label encoding
            print("[Agent1] No target column supplied -> using frequency encoding "
                  "instead of target encoding.")
            for col in cat_cols:
                col_str = df[col].astype(object).astype(str)
                freq = col_str.value_counts(normalize=True)
                df[col] = col_str.map(freq).astype("float32")
            return df

        print(f"[Agent1] Target-encoding {len(cat_cols)} categorical column(s) via "
              f"{n_splits}-fold out-of-fold mean encoding ...")

        # Cast to plain string first -- avoids pandas 'category'/StringDtype
        # edge cases when building fold-wise groupby maps below.
        for col in cat_cols:
            df[col] = df[col].astype(object).astype(str)

        y = df[self.target_col]
        self.global_target_mean_ = float(y.mean())
        kf = KFold(n_splits=n_splits, shuffle=True, random_state=self.random_state)

        for col in cat_cols:
            oof_encoded = pd.Series(np.nan, index=df.index, dtype="float64")
            for train_idx, val_idx in kf.split(df):
                fold_map = df.iloc[train_idx].groupby(col)[self.target_col].mean()
                mapped = df.iloc[val_idx][col].map(fold_map).astype("float64")
                oof_encoded.iloc[val_idx] = mapped.values
            oof_encoded = oof_encoded.fillna(self.global_target_mean_)
            df[col] = oof_encoded.astype("float32")

            # Store a full-data mapping to use at inference time on new data
            self.target_encoding_maps_[col] = df.groupby(col)[self.target_col].mean()

        return df

    # ------------------------------------------------------------------ #
    # 3. TREE-BASED ITERATIVE MISSING VALUE IMPUTATION
    # ------------------------------------------------------------------ #
    def impute_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if self.target_col in numeric_cols:
            numeric_cols.remove(self.target_col)
        self.numeric_cols_ = numeric_cols

        if not numeric_cols:
            return df

        missing_frac = df[numeric_cols].isna().mean()
        if missing_frac.sum() == 0:
            print("[Agent1] No missing values detected -> skipping imputation.")
            return df

        print(f"[Agent1] Imputing missing values on {len(numeric_cols)} numeric "
              f"columns using an XGBoost-driven IterativeImputer ...")

        # Tree-based estimator plugged into sklearn's iterative (MICE-style) imputer.
        tree_estimator = xgb.XGBRegressor(
            n_estimators=50,
            max_depth=4,
            learning_rate=0.3,
            tree_method="hist",
            n_jobs=-1,
            random_state=self.random_state,
            verbosity=0,
        )

        self.imputer_ = IterativeImputer(
            estimator=tree_estimator,
            max_iter=5,           # kept small for large-data efficiency
            n_nearest_features=10,  # cap columns used per imputation for speed
            sample_posterior=False,
            random_state=self.random_state,
        )

        imputed = self.imputer_.fit_transform(df[numeric_cols])
        df[numeric_cols] = imputed.astype("float32")

        # Any remaining non-numeric NaNs (rare) -> most-frequent fallback
        remaining_na_cols = [c for c in df.columns if df[c].isna().any()]
        if remaining_na_cols:
            simple = SimpleImputer(strategy="most_frequent")
            df[remaining_na_cols] = simple.fit_transform(df[remaining_na_cols])

        return df

    # ------------------------------------------------------------------ #
    # 4. XGBOOST FEATURE-IMPORTANCE-BASED SELECTION
    # ------------------------------------------------------------------ #
    def select_features_by_importance(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.target_col is None or self.target_col not in df.columns:
            print("[Agent1] No target column -> skipping importance-based selection "
                  "(keeping all engineered features).")
            self.selected_features_ = [c for c in df.columns if c != self.target_col]
            return df

        feature_cols = [c for c in df.columns if c != self.target_col]
        X, y = df[feature_cols], df[self.target_col]

        is_classification = y.nunique() <= 20 and y.dtype != float
        model_cls = xgb.XGBClassifier if is_classification else xgb.XGBRegressor
        objective = "binary:logistic" if (is_classification and y.nunique() == 2) else (
            "multi:softprob" if is_classification else "reg:squarederror"
        )

        print(f"[Agent1] Ranking {len(feature_cols)} features via XGBoost "
              f"({'classification' if is_classification else 'regression'}) importances ...")

        model_kwargs = dict(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            tree_method="hist",
            n_jobs=-1,
            random_state=self.random_state,
            verbosity=0,
        )
        if is_classification and y.nunique() > 2:
            model_kwargs["num_class"] = int(y.nunique())
        model_kwargs["objective"] = objective

        model = model_cls(**model_kwargs)
        model.fit(X, y)

        importances = pd.Series(model.feature_importances_, index=feature_cols)
        importances = importances.sort_values(ascending=False)
        self.feature_importances_ = importances

        if self.importance_top_k:
            selected = importances.head(self.importance_top_k).index.tolist()
        elif self.importance_threshold:
            selected = importances[importances >= self.importance_threshold].index.tolist()
        else:
            # default heuristic: keep features carrying 99% of cumulative importance
            cum = importances.cumsum() / importances.sum()
            selected = cum[cum <= 0.99].index.tolist() or importances.head(1).index.tolist()

        print(f"[Agent1] Selected {len(selected)}/{len(feature_cols)} features.")
        self.selected_features_ = selected

        keep_cols = selected + ([self.target_col] if self.target_col in df.columns else [])
        return df[keep_cols]

    # ------------------------------------------------------------------ #
    # 5. POWER TRANSFORM + SCALING
    # ------------------------------------------------------------------ #
    def power_transform_and_scale(self, df: pd.DataFrame) -> pd.DataFrame:
        feature_cols = [c for c in df.columns if c != self.target_col]
        if not feature_cols:
            return df

        print(f"[Agent1] Applying Yeo-Johnson power transform + standard scaling "
              f"to {len(feature_cols)} columns ...")

        self.power_transformer_ = PowerTransformer(method="yeo-johnson", standardize=False)
        transformed = self.power_transformer_.fit_transform(df[feature_cols])

        self.scaler_ = StandardScaler()
        scaled = self.scaler_.fit_transform(transformed)

        df[feature_cols] = scaled.astype("float32")
        return df

    # ------------------------------------------------------------------ #
    # ORCHESTRATION
    # ------------------------------------------------------------------ #
    def fit_transform(self, source: Union[str, pd.DataFrame]) -> pd.DataFrame:
        """Run the full Agent-1 pipeline end to end and return the clean dataframe."""
        print("=" * 80)
        print("[Agent1] STARTING DATA INGESTION & PREPROCESSING PIPELINE")
        print("=" * 80)

        df = self.load_data(source)
        df = self.encode_categoricals(df)
        df = self.impute_missing(df)
        df = self.select_features_by_importance(df)
        df = self.power_transform_and_scale(df)

        print(f"[Agent1] DONE. Final clean dataset shape -> {df.shape}")
        print("=" * 80)
        return df


# ========================================================================= #
# Standalone smoke test
# ========================================================================= #
if __name__ == "__main__":
    rng = np.random.default_rng(42)
    n = 5_000
    demo_df = pd.DataFrame({
        "amount": rng.exponential(scale=200, size=n),
        "age": rng.normal(40, 12, size=n),
        "city": rng.choice(["NYC", "LA", "SF", "Chicago", "Houston", "Miami"], size=n),
        "device": rng.choice(["mobile", "desktop", "tablet"], size=n),
        "target": rng.integers(0, 2, size=n),
    })
    # inject missing values + noise
    demo_df.loc[rng.choice(n, 300, replace=False), "amount"] = np.nan
    demo_df.loc[rng.choice(n, 150, replace=False), "age"] = np.nan

    agent1 = DataIngestionAgent(target_col="target", importance_threshold=None)
    clean_df = agent1.fit_transform(demo_df)
    print(clean_df.head())
