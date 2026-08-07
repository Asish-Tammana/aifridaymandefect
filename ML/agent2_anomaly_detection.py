"""
=====================================================================================
 AGENT 2: ANOMALY DETECTION AGENT
=====================================================================================
Role
----
Consumes the clean, scaled dataframe produced by Agent 1 and flags anomalies
using LightGBM, configured for fast training on large datasets (histogram
binning, leaf-wise growth, feature/bagging fraction sub-sampling).

Two operating modes are supported:

  * SUPERVISED  — a binary label column (1 = anomaly, 0 = normal) is present.
                  A standard LightGBM binary classifier is trained on it.

  * UNSUPERVISED — no labels are available (the common real-world case for
                  anomaly detection). The agent manufactures a synthetic
                  "anomaly" class by sampling points uniformly at random
                  inside the feature-space bounding box of the real data
                  (a standard "classifier-based novelty/outlier detection"
                  trick: real data = class 0, synthetic uniform noise =
                  class 1). LightGBM then learns a decision boundary that
                  separates dense, structured real regions from the
                  unstructured synthetic ones — points that resemble the
                  synthetic distribution (i.e. sit in low-density regions
                  of the real data) score as anomalies.

Output
------
For every input record:
  * predicted_label        -> 0 (normal) / 1 (anomaly)
  * anomaly_probability_%  -> exact anomaly score as a 0-100% probability

Author: ML Engineering reference implementation
=====================================================================================
"""

import warnings
from typing import Optional

import numpy as np
import pandas as pd
import lightgbm as lgb

from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report

warnings.filterwarnings("ignore")


class AnomalyDetectionAgent:
    """
    Agent 2 — trains a fast LightGBM model and scores every record with an
    exact anomaly probability (0-100%) plus a binary anomaly label.

    Parameters
    ----------
    contamination : float
        Expected proportion of anomalies in the data (0 < x < 0.5). Used to
        pick the decision threshold when no labels / no fixed 0.5 cut is
        appropriate, and to size the synthetic anomaly set in unsupervised mode.
    synthetic_multiplier : float
        In unsupervised mode, how many synthetic anomaly rows to generate
        relative to the real row count (1.0 = same size, balanced classes).
    n_estimators, max_depth, learning_rate, num_leaves : LightGBM hyperparameters
        Tuned defaults favor speed on large tabular datasets.
    random_state : int
        Reproducibility seed.
    """

    def __init__(
        self,
        contamination: float = 0.05,
        synthetic_multiplier: float = 1.0,
        n_estimators: int = 400,
        max_depth: int = -1,
        num_leaves: int = 63,
        learning_rate: float = 0.05,
        random_state: int = 42,
    ):
        self.contamination = contamination
        self.synthetic_multiplier = synthetic_multiplier
        self.random_state = random_state

        # LightGBM params tuned for FAST training on large datasets:
        # - histogram-based binning (default in lgb)
        # - leaf-wise growth with capped num_leaves to avoid overfit/slowdown
        # - feature_fraction / bagging_fraction sub-sampling for speed
        # - n_jobs=-1 to use all cores
        self.model_params = dict(
            objective="binary",
            boosting_type="gbdt",
            n_estimators=n_estimators,
            max_depth=max_depth,
            num_leaves=num_leaves,
            learning_rate=learning_rate,
            feature_fraction=0.8,
            bagging_fraction=0.8,
            bagging_freq=5,
            max_bin=255,
            n_jobs=-1,
            random_state=random_state,
            verbosity=-1,
        )

        self.model_: Optional[lgb.LGBMClassifier] = None
        self.threshold_: float = 0.5
        self.mode_: str = "unsupervised"
        self.feature_cols_: list = []

    # ------------------------------------------------------------------ #
    # Synthetic anomaly generation (used only when no labels are given)
    # ------------------------------------------------------------------ #
    def _generate_synthetic_anomalies(self, X: pd.DataFrame) -> pd.DataFrame:
        n_synth = int(len(X) * self.synthetic_multiplier)
        rng = np.random.default_rng(self.random_state)

        synth = pd.DataFrame(index=range(n_synth), columns=X.columns, dtype="float32")
        for col in X.columns:
            lo, hi = X[col].min(), X[col].max()
            # widen bounds slightly so synthetic points can also fall
            # just outside the observed range (classic outlier behaviour)
            pad = 0.1 * (hi - lo + 1e-9)
            synth[col] = rng.uniform(lo - pad, hi + pad, size=n_synth)
        return synth

    def _build_training_set(self, X: pd.DataFrame, y: Optional[pd.Series]):
        if y is not None:
            self.mode_ = "supervised"
            print("[Agent2] Label column detected -> training in SUPERVISED mode.")
            return X, y.astype(int)

        self.mode_ = "unsupervised"
        print("[Agent2] No labels supplied -> training in UNSUPERVISED mode "
              "(real data vs. synthetic uniform-noise anomalies).")
        synth = self._generate_synthetic_anomalies(X)

        X_train = pd.concat([X.reset_index(drop=True), synth.reset_index(drop=True)],
                             axis=0, ignore_index=True)
        y_train = pd.Series([0] * len(X) + [1] * len(synth))
        return X_train, y_train

    # ------------------------------------------------------------------ #
    # FIT
    # ------------------------------------------------------------------ #
    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None):
        self.feature_cols_ = X.columns.tolist()
        X_train_full, y_train_full = self._build_training_set(X, y)

        X_tr, X_val, y_tr, y_val = train_test_split(
            X_train_full, y_train_full,
            test_size=0.2,
            stratify=y_train_full,
            random_state=self.random_state,
        )

        print(f"[Agent2] Training LightGBM on {len(X_tr):,} rows "
              f"({X_tr.shape[1]} features) ...")

        self.model_ = lgb.LGBMClassifier(**self.model_params)
        self.model_.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            eval_metric="auc",
            callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False),
                       lgb.log_evaluation(period=0)],
        )

        val_proba = self.model_.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, val_proba)
        print(f"[Agent2] Validation AUC: {auc:.4f}")

        # Decide the operating threshold
        if self.mode_ == "supervised":
            self.threshold_ = 0.5
        else:
            # In unsupervised mode, calibrate threshold on the REAL data only
            # so that ~`contamination` fraction of real rows are flagged.
            real_scores = self.model_.predict_proba(X)[:, 1]
            self.threshold_ = float(np.quantile(real_scores, 1 - self.contamination))
            print(f"[Agent2] Threshold calibrated at the {1 - self.contamination:.0%} "
                  f"quantile of real-data anomaly scores -> {self.threshold_:.4f}")

        return self

    # ------------------------------------------------------------------ #
    # PREDICT
    # ------------------------------------------------------------------ #
    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        if self.model_ is None:
            raise RuntimeError("Call `.fit()` (or `.fit_predict()`) before predicting.")

        X = X[self.feature_cols_]
        proba_anomaly = self.model_.predict_proba(X)[:, 1]
        labels = (proba_anomaly >= self.threshold_).astype(int)

        result = pd.DataFrame({
            "predicted_label": labels,
            "anomaly_probability_%": np.round(proba_anomaly * 100, 2),
        }, index=X.index)
        return result

    def fit_predict(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> pd.DataFrame:
        self.fit(X, y)
        return self.predict(X)

    # ------------------------------------------------------------------ #
    # Evaluation helper (only meaningful if ground-truth labels exist)
    # ------------------------------------------------------------------ #
    def evaluate(self, X: pd.DataFrame, y_true: pd.Series):
        preds = self.predict(X)
        print(classification_report(y_true, preds["predicted_label"]))
        print(f"AUC: {roc_auc_score(y_true, preds['anomaly_probability_%'] / 100):.4f}")


# ========================================================================= #
# Standalone smoke test
# ========================================================================= #
if __name__ == "__main__":
    rng = np.random.default_rng(7)
    n_normal = 4_800
    n_anom = 200

    normal = pd.DataFrame(rng.normal(0, 1, size=(n_normal, 5)),
                           columns=[f"f{i}" for i in range(5)])
    anomalies = pd.DataFrame(rng.normal(6, 1.5, size=(n_anom, 5)),
                              columns=[f"f{i}" for i in range(5)])

    demo_X = pd.concat([normal, anomalies], ignore_index=True)

    agent2 = AnomalyDetectionAgent(contamination=n_anom / (n_normal + n_anom))
    results = agent2.fit_predict(demo_X)  # unsupervised mode (no y passed)

    print(results.head(10))
    print(f"\nFlagged {results['predicted_label'].sum()} anomalies out of {len(results)} rows.")
