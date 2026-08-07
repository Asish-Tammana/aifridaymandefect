"""
=====================================================================================
 FULL EXECUTION WORKFLOW: Agent1 (Ingestion/Preprocessing) -> Agent2 (Anomaly Detection)
=====================================================================================
Wires the two agents together end to end:

  raw noisy data --> [Agent 1: DataIngestionAgent] --> clean scaled data
                  --> [Agent 2: AnomalyDetectionAgent] --> labels + probabilities

Run:  python main_pipeline.py
=====================================================================================
"""

import numpy as np
import requests
import pandas as pd

from agent1_data_ingestion_preprocessing import DataIngestionAgent
from agent2_anomaly_detection import AnomalyDetectionAgent


def generate_synthetic_raw_data(n_rows: int = 20_000, anomaly_frac: float = 0.03,
                                 random_state: int = 42) -> pd.DataFrame:
    """Simulates a large, messy raw dataset (transactions-style) with
    missing values, noisy categoricals, and an injected anomalous subset."""
    rng = np.random.default_rng(random_state)
    n_anom = int(n_rows * anomaly_frac)
    n_normal = n_rows - n_anom

    normal = pd.DataFrame({
        "transaction_amount": rng.exponential(scale=120, size=n_normal),
        "customer_age": rng.normal(38, 10, size=n_normal),
        "account_tenure_days": rng.gamma(shape=5, scale=200, size=n_normal),
        "merchant_category": rng.choice(
            ["grocery", "electronics", "travel", "utilities", "dining", "fashion"],
            size=n_normal, p=[0.3, 0.15, 0.1, 0.2, 0.15, 0.1]),
        "device_type": rng.choice(["mobile", "desktop", "tablet"], size=n_normal),
        "is_anomaly": 0,
    })

    anomalies = pd.DataFrame({
        "transaction_amount": rng.exponential(scale=120, size=n_anom) * rng.uniform(6, 15, n_anom),
        "customer_age": rng.normal(38, 10, size=n_anom),
        "account_tenure_days": rng.uniform(0, 5, size=n_anom),  # brand-new accounts
        "merchant_category": rng.choice(
            ["electronics", "travel", "fashion"], size=n_anom),
        "device_type": rng.choice(["mobile", "desktop", "tablet"], size=n_anom),
        "is_anomaly": 1,
    })

    df = pd.concat([normal, anomalies], ignore_index=True).sample(
        frac=1.0, random_state=random_state).reset_index(drop=True)

    # inject realistic missingness/noise
    na_idx = rng.choice(df.index, size=int(0.03 * len(df)), replace=False)
    df.loc[na_idx, "transaction_amount"] = np.nan
    na_idx2 = rng.choice(df.index, size=int(0.02 * len(df)), replace=False)
    df.loc[na_idx2, "account_tenure_days"] = np.nan

    return df


def run_pipeline(raw_df: pd.DataFrame, label_col: str = "is_anomaly",
                  use_labels_for_training: bool = False):
    """
    Executes the two-agent workflow.

    use_labels_for_training:
        False -> Agent1 still uses `is_anomaly` internally as a supervisory
                 signal for target-encoding/feature-importance, but Agent2
                 is run in pure UNSUPERVISED mode (labels withheld), which
                 mirrors real-world anomaly detection where fraud/anomaly
                 labels are typically unavailable at inference time.
        True  -> Agent2 is trained SUPERVISED using the real label column,
                 useful for benchmarking against ground truth.
    """
    # ---------------- AGENT 1 ----------------
    agent1 = DataIngestionAgent(
        target_col=label_col,
        chunksize=5_000,
        importance_threshold=None,  # use default 99% cumulative-importance heuristic
    )
    clean_df = agent1.fit_transform(raw_df)

    y_true = clean_df.pop(label_col) if label_col in clean_df.columns else None

    # ---------------- AGENT 2 ----------------
    agent2 = AnomalyDetectionAgent(
        contamination=float(y_true.mean()) if y_true is not None else 0.05,
    )

    if use_labels_for_training and y_true is not None:
        results = agent2.fit_predict(clean_df, y_true)
    else:
        results = agent2.fit_predict(clean_df)  # unsupervised

    final_output = pd.concat(
        [raw_df.reset_index(drop=True), results.reset_index(drop=True)], axis=1
    )

    if y_true is not None:
        print("\n[Pipeline] Ground-truth comparison:")
        agent2.evaluate(clean_df, y_true)

    return final_output, agent1, agent2


if __name__ == "__main__":
    # Existing API that provides the input data
    input_api_url = "http://127.0.0.1:8000/events/latest"

    # Input required by that API
    api_input = {
        "machine_id": 101,
        "start_date": "2026-08-01",
        "end_date": "2026-08-07",
    }

    response = requests.get(
    "http://127.0.0.1:8000/events/latest",
    params={
        "machine_id": 101,
        "start_date": "2026-08-01",
        "end_date": "2026-08-07",
    },
    timeout=300,
)

    print("Requested URL:", response.url)
    print("Status code:", response.status_code)
    print("Response body:", response.text)

    if not response.ok:
        raise RuntimeError(
        f"Input API failed with HTTP {response.status_code}: "
        f"{response.text}"
    )

    api_output = response.json()

    if not isinstance(api_output, dict):
        raise ValueError("Expected the API to return a JSON object.")

# Flatten nested JSON fields and create one DataFrame row.
    raw_data = pd.json_normalize([api_output])

    print(f"[Pipeline] API input shape: {raw_data.shape}")
    print(f"[Pipeline] API columns: {raw_data.columns.tolist()}")


    output_df, agent1, agent2 = run_pipeline(
        raw_data,
        label_col=None,
        use_labels_for_training=False,
    )

    prediction_cols = [
        "predicted_label",
        "anomaly_probability_%",
    ]

    preview_cols = list(raw_data.columns[:3])
    preview_cols += [
        column
        for column in prediction_cols
        if column in output_df.columns
    ]

    print("\n[Pipeline] Sample output:")
    print(output_df[preview_cols].head(10))

    output_df.to_csv("pipeline_output.csv", index=False)
    print("\n[Pipeline] Results saved to pipeline_output.csv")