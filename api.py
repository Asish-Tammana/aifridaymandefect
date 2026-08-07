"""
Flask REST API backend for the React frontend.
Exposes endpoints for Dashboard, Producer, Analytics, and Metrics pages.

Run with: python api.py
"""

import os
import json
import sqlite3
import hashlib
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "model")

QUEUE_PATH = os.path.join(DATA_DIR, "live_queue.csv")
ALERTS_PATH = os.path.join(DATA_DIR, "alerts.csv")
FEEDBACK_PATH = os.path.join(DATA_DIR, "feedback.csv")
PROCESSED_MARKER = os.path.join(DATA_DIR, ".processed_batch_ids.txt")
POOL_PATH = os.path.join(DATA_DIR, "log_pool.csv")
DEFECTS_PATH = os.path.join(DATA_DIR, "defects_data.csv")
AI4I_PATH = os.path.join(DATA_DIR, "ai4i2020.csv")
DATASET_PATH = os.path.join(DATA_DIR, "dataset.csv")
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")
DB_PATH = os.path.join(DATA_DIR, "users.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    # Default admin user
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                  ('admin', hashlib.sha256('admin'.encode()).hexdigest(), 'ADMIN'))
    conn.commit()
    conn.close()

init_db()

ALERT_COLUMNS = [
    "batch_id", "timestamp", "machine_id", "product_type",
    "risk_score", "risk_level",
    "air_temp_K", "process_temp_K", "rpm", "torque_Nm",
    "tool_wear_min", "power_W", "temp_diff",
    "deviated_params", "probable_cause", "recommended_action",
    "confidence", "needs_human_review",
]

HIDDEN_COLS = {"ground_truth_label", "failure_modes", "Machine failure", "TWF", "HDF", "PWF", "OSF", "RNF"}


# ─── Helpers ───────────────────────────────────────────────────────────────

def load_processed_ids():
    if os.path.exists(PROCESSED_MARKER):
        with open(PROCESSED_MARKER) as f:
            return {line.strip() for line in f if line.strip()}
    return set()


def mark_processed(batch_id):
    with open(PROCESSED_MARKER, "a") as f:
        f.write(f"{batch_id}\n")


def load_alerts():
    if os.path.exists(ALERTS_PATH):
        df = pd.read_csv(ALERTS_PATH)
        return df
    return pd.DataFrame(columns=ALERT_COLUMNS)


def append_alert(alert):
    df = pd.DataFrame([alert])
    header = not os.path.exists(ALERTS_PATH)
    df.to_csv(ALERTS_PATH, mode="a", header=header, index=False)


def safe_json(df):
    """Convert DataFrame to JSON-safe records."""
    return json.loads(df.to_json(orient="records"))

# ─── Auth endpoints ────────────────────────────────────────────────────────
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "USER")
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
        
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                  (username, password_hash, role))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "User created successfully"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
        
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE username=? AND password_hash=?", 
              (username, password_hash))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({"success": True, "user": {"id": user[0], "username": user[1], "role": user[2]}})
    else:
        return jsonify({"error": "Invalid credentials"}), 401


# ─── Dashboard endpoints ────────────────────────────────────────────────────

@app.route("/api/dashboard/process", methods=["POST"])
def process_batches():
    """Process any new batches from the queue."""
    if not os.path.exists(QUEUE_PATH):
        return jsonify({"processed": 0, "message": "No queue file yet. Push batches from the Producer page."})

    try:
        try:
            from graph import process_batch
        except ImportError as ie:
            return jsonify({"processed": 0, "error": f"Missing dependency: {ie}. Run: pip install -r requirements.txt"}), 200

        queue_df = pd.read_csv(QUEUE_PATH)
        id_col = "Product ID" if "Product ID" in queue_df.columns else "batch_id"
        processed_ids = load_processed_ids()
        new_rows = queue_df[~queue_df[id_col].isin(processed_ids)]

        if len(new_rows) == 0:
            return jsonify({"processed": 0, "message": "No new batches to process."})

        for _, row in new_rows.iterrows():
            alert = process_batch(row.to_dict())
            append_alert(alert)
            mark_processed(row[id_col])

        return jsonify({"processed": len(new_rows)})
    except Exception as e:
        return jsonify({"error": str(e), "processed": 0}), 500


@app.route("/api/dashboard/alerts", methods=["GET"])
def get_alerts():
    """Get all alerts with KPI summary."""
    alerts_df = load_alerts()
    if not alerts_df.empty and "batch_id" in alerts_df.columns:
        alerts_df = alerts_df.drop_duplicates(subset=["batch_id"], keep="last")

    if alerts_df.empty:
        return jsonify({
            "alerts": [],
            "kpis": {"total": 0, "high": 0, "medium": 0, "needs_review": 0}
        })

    kpis = {
        "total": len(alerts_df),
        "high": int((alerts_df["risk_level"] == "High").sum()),
        "medium": int((alerts_df["risk_level"] == "Medium").sum()),
        "needs_review": int(alerts_df["needs_human_review"].sum()) if "needs_human_review" in alerts_df.columns else 0,
    }

    sorted_df = alerts_df.sort_values("timestamp", ascending=False)
    return jsonify({"alerts": safe_json(sorted_df), "kpis": kpis})


@app.route("/api/dashboard/batch/<batch_id>", methods=["GET"])
def get_batch_detail(batch_id):
    """Get detail for a specific batch."""
    alerts_df = load_alerts()
    row = alerts_df[alerts_df["batch_id"] == batch_id]
    if row.empty:
        return jsonify({"error": "Batch not found"}), 404
    return jsonify(row.iloc[0].to_dict())


@app.route("/api/dashboard/retry/<batch_id>", methods=["POST"])
def retry_batch(batch_id):
    """Retry AI analysis for a failed batch."""
    try:
        from graph import process_batch
        queue_df = pd.read_csv(QUEUE_PATH)
        id_col = "Product ID" if "Product ID" in queue_df.columns else "batch_id"
        batch_data = queue_df[queue_df[id_col] == batch_id].iloc[0].to_dict()

        new_alert = process_batch(batch_data)

        alerts = pd.read_csv(ALERTS_PATH)
        alerts = alerts[alerts["batch_id"] != batch_id]
        alerts = pd.concat([alerts, pd.DataFrame([new_alert])], ignore_index=True)
        alerts.to_csv(ALERTS_PATH, index=False)

        return jsonify({"success": True, "alert": new_alert})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboard/feedback", methods=["POST"])
def submit_feedback():
    """Submit operator feedback for a batch."""
    data = request.json
    batch_id = data.get("batch_id")
    feedback = data.get("feedback")
    correction = data.get("correction", "")

    entry = {"batch_id": batch_id, "feedback": feedback, "correction": correction}
    pd.DataFrame([entry]).to_csv(
        FEEDBACK_PATH, mode="a", header=not os.path.exists(FEEDBACK_PATH), index=False
    )
    return jsonify({"success": True})


@app.route("/api/dashboard/chat", methods=["POST"])
def chat():
    """AI chatbot for a specific batch."""
    data = request.json
    batch_id = data.get("batch_id")
    prompt = data.get("prompt")

    alerts_df = load_alerts()
    row_df = alerts_df[alerts_df["batch_id"] == batch_id]
    if row_df.empty:
        return jsonify({"error": "Batch not found"}), 404

    row = row_df.iloc[0]
    context = f"""
    You are a manufacturing AI assistant helping an operator. The user is asking about batch {batch_id}.
    Risk level: {row['risk_level']} (Score: {row['risk_score']})
    Deviated parameters: {row.get('deviated_params', 'none')}
    Probable cause determined earlier: {row.get('probable_cause', 'unknown')}
    Sensor readings: Air Temp {row.get('air_temp_K')}K, Process Temp {row.get('process_temp_K')}K, RPM {row.get('rpm')}, Torque {row.get('torque_Nm')}Nm, Wear {row.get('tool_wear_min')}min.
    Engineered features: Power {row.get('power_W')}W, Temp Diff {row.get('temp_diff')}K.

    User question: {prompt}

    Please provide a helpful, concise answer based on this context. Do not use markdown code blocks unless necessary.
    """

    try:
        from llm_client import llm_call
        response = llm_call(context)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Producer endpoints ─────────────────────────────────────────────────────

@app.route("/api/producer/status", methods=["GET"])
def producer_status():
    """Get producer page status."""
    if not os.path.exists(POOL_PATH):
        return jsonify({"error": "Pool not found. Run generate_dataset.py first."}), 404

    pool_df = pd.read_csv(POOL_PATH)
    pushed_count = 0

    if os.path.exists(QUEUE_PATH):
        pushed_ids = set(pd.read_csv(QUEUE_PATH)["Product ID"])
        pushed_count = int(pool_df["Product ID"].isin(pushed_ids).sum())

    n_failures = int(pool_df["ground_truth_label"].value_counts().get("FAILURE", 0))
    remaining = len(pool_df) - pushed_count

    # Preview next 5 rows
    COLUMNS_TO_PUSH = [c for c in pool_df.columns if c not in HIDDEN_COLS]
    highlight_cols = ["Product ID", "Type", "Air temperature [K]",
                      "Process temperature [K]", "Rotational speed [rpm]",
                      "Torque [Nm]", "Tool wear [min]",
                      "ground_truth_label", "failure_modes"]
    available = [c for c in highlight_cols if c in pool_df.columns]
    preview = pool_df.iloc[pushed_count:pushed_count + 5][available]

    # Failure mode breakdown
    failure_modes = {}
    if "failure_modes" in pool_df.columns:
        modes = pool_df["failure_modes"].dropna().replace("", pd.NA).dropna()
        all_modes = []
        for m in modes:
            all_modes.extend(str(m).split(","))
        if all_modes:
            failure_modes = pd.Series(all_modes).value_counts().to_dict()

    return jsonify({
        "pushed_count": pushed_count,
        "remaining": remaining,
        "total": len(pool_df),
        "n_failures": n_failures,
        "preview": safe_json(preview),
        "failure_modes": failure_modes,
        "failure_rate": round(n_failures / len(pool_df) * 100, 1),
    })


@app.route("/api/producer/push", methods=["POST"])
def push_batch():
    """Push next N batches from pool to queue."""
    data = request.json or {}
    batch_size = data.get("batch_size", 5)

    if not os.path.exists(POOL_PATH):
        return jsonify({"error": "Pool not found"}), 404

    pool_df = pd.read_csv(POOL_PATH)
    pushed_count = 0

    if os.path.exists(QUEUE_PATH):
        pushed_ids = set(pd.read_csv(QUEUE_PATH)["Product ID"])
        pushed_count = int(pool_df["Product ID"].isin(pushed_ids).sum())

    COLUMNS_TO_PUSH = [c for c in pool_df.columns if c not in HIDDEN_COLS]
    start = pushed_count
    end = min(start + batch_size, len(pool_df))
    new_rows = pool_df.iloc[start:end][COLUMNS_TO_PUSH]

    if len(new_rows) == 0:
        return jsonify({"pushed": 0, "message": "No more batches to push"})

    header = not os.path.exists(QUEUE_PATH)
    new_rows.to_csv(QUEUE_PATH, mode="a", header=header, index=False)

    pushed_slice = pool_df.iloc[start:end]
    n_fail = int((pushed_slice["ground_truth_label"] == "FAILURE").sum())

    return jsonify({
        "pushed": len(new_rows),
        "n_failures": n_fail,
        "message": f"Pushed {len(new_rows)} batch(es)" + (f" — {n_fail} contain failures" if n_fail else " — all normal"),
    })


@app.route("/api/producer/reset", methods=["POST"])
def reset_simulation():
    """Reset the simulation."""
    for fpath in [QUEUE_PATH, PROCESSED_MARKER, ALERTS_PATH, FEEDBACK_PATH]:
        if os.path.exists(fpath):
            os.remove(fpath)
    return jsonify({"success": True})


# ─── Analytics endpoints ────────────────────────────────────────────────────

@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    """Get analytics data."""
    result = {}

    # Defects
    if os.path.exists(DEFECTS_PATH):
        df = pd.read_csv(DEFECTS_PATH)
        result["kpis"] = {
            "total_defects": len(df),
            "total_cost": float(df["repair_cost"].sum()),
            "avg_cost": float(df["repair_cost"].mean()),
            "critical_count": int((df["severity"] == "Critical").sum()),
        }
        result["defect_types"] = df["defect_type"].value_counts().to_dict()
        result["severity"] = df["severity"].value_counts().to_dict()
        result["inspection_methods"] = df["inspection_method"].value_counts().to_dict()
        result["defect_locations"] = df["defect_location"].value_counts().head(10).to_dict()

        if "failure_mode" in df.columns:
            result["failure_modes"] = df["failure_mode"].value_counts().to_dict()

        if "machine_id" in df.columns:
            machine_df = df.groupby("machine_id").agg(
                defect_count=("defect_id", "count"),
                total_cost=("repair_cost", "sum"),
                critical_count=("severity", lambda x: (x == "Critical").sum()),
            ).sort_values("defect_count", ascending=False)
            result["machine_defects"] = safe_json(machine_df.reset_index())

        cost_by_type = df.groupby("defect_type")["repair_cost"].agg(["mean", "sum", "count"]).reset_index()
        cost_by_type.columns = ["defect_type", "avg_cost", "total_cost", "count"]
        result["cost_by_type"] = safe_json(cost_by_type)
    else:
        result["error"] = "No defect data. Run generate_dataset.py first."

    # AI4I2020
    if os.path.exists(AI4I_PATH):
        ai4i = pd.read_csv(AI4I_PATH)
        type_dist = ai4i["Type"].value_counts().to_dict()
        result["ai4i"] = {
            "total": len(ai4i),
            "failure_rate": round(float(ai4i["Machine failure"].mean()) * 100, 1),
            "type_dist": type_dist,
        }
        sensor_cols = ["Air temperature [K]", "Process temperature [K]",
                       "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]"]
        result["sensor_distributions"] = {}
        for col in sensor_cols:
            if col in ai4i.columns:
                result["sensor_distributions"][col] = ai4i[col].tolist()[:200]

    # Dataset
    if os.path.exists(DATASET_PATH):
        ds = pd.read_csv(DATASET_PATH)
        result["dataset"] = {
            "status_counts": ds["Machine_Status"].value_counts().to_dict() if "Machine_Status" in ds.columns else {},
            "quality_pass_rate": round(ds["Quality_Check"].value_counts().get(True, 0) / len(ds) * 100, 1) if "Quality_Check" in ds.columns else 0,
            "total_products": int(ds["Product_Count"].max()) if "Product_Count" in ds.columns else 0,
        }

    return jsonify(result)


# ─── Metrics endpoints ──────────────────────────────────────────────────────

@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Get model metrics and ROI data."""
    result = {}

    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH) as f:
            metrics = json.load(f)
        result["model"] = metrics
    else:
        result["model"] = None

    # ROI
    avg_cost = 912
    if os.path.exists(DEFECTS_PATH):
        df = pd.read_csv(DEFECTS_PATH)
        if not df.empty and "repair_cost" in df.columns:
            avg_cost = float(df["repair_cost"].mean())

    if os.path.exists(POOL_PATH) and os.path.exists(METRICS_PATH):
        pool = pd.read_csv(POOL_PATH)
        failures = int((pool["ground_truth_label"] == "FAILURE").sum())
        with open(METRICS_PATH) as f:
            m = json.load(f)
        recall = m.get("recall", 0.95)
        caught = int(failures * recall)
        missed = failures - caught
        result["roi"] = {
            "total_failures": failures,
            "caught": caught,
            "missed": missed,
            "saved_cost": round(caught * avg_cost, 2),
            "exposed_cost": round(missed * avg_cost, 2),
            "avg_cost": round(avg_cost, 2),
        }

    # Feedback
    if os.path.exists(FEEDBACK_PATH):
        fb_df = pd.read_csv(FEEDBACK_PATH)
        if not fb_df.empty:
            total = len(fb_df)
            upvotes = int((fb_df["feedback"] == "up").sum())
            corrections = int(fb_df["correction"].notna().sum())
            result["feedback"] = {
                "total": total,
                "upvotes": upvotes,
                "helpful_ratio": round(upvotes / total * 100),
                "corrections": corrections,
                "records": safe_json(fb_df),
            }

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
