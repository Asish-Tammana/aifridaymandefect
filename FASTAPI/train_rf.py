import os
import sqlite3
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score

DB_PATH = "mes.db"
MODEL_DIR = "."

def train():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database file '{DB_PATH}' not found. Please run seed_bulk.py first.")

    print("Loading data from database...")
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT temperature, vibration, humidity, pressure, rotations_per_minute, failure_category, severity 
        FROM events
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    print(f"Loaded {len(df)} rows.")

    # Fill missing values if any
    df = df.dropna(subset=["temperature", "vibration", "humidity", "pressure", "rotations_per_minute"])
    
    # Handle failure_category (replace None with 'None')
    df["failure_category"] = df["failure_category"].fillna("None")
    df["severity"] = df["severity"].fillna("NORMAL")

    features = ["temperature", "vibration", "humidity", "pressure", "rotations_per_minute"]
    X = df[features]

    # Target 1: failure_category
    y_cat = df["failure_category"]
    le_cat = LabelEncoder()
    y_cat_encoded = le_cat.fit_transform(y_cat)

    # Target 2: severity
    y_sev = df["severity"]
    le_sev = LabelEncoder()
    y_sev_encoded = le_sev.fit_transform(y_sev)

    print("\nTraining Failure Category Model...")
    X_train, X_test, y_train, y_test = train_test_split(X, y_cat_encoded, test_size=0.2, random_state=42, stratify=y_cat_encoded)
    
    rf_cat = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
    rf_cat.fit(X_train, y_train)
    y_pred = rf_cat.predict(X_test)
    print(f"Category Model Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(classification_report(y_test, y_pred, target_names=le_cat.classes_))

    print("\nTraining Severity Model...")
    X_train_s, X_test_s, y_train_s, y_test_s = train_test_split(X, y_sev_encoded, test_size=0.2, random_state=42, stratify=y_sev_encoded)
    
    rf_sev = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
    rf_sev.fit(X_train_s, y_train_s)
    y_pred_s = rf_sev.predict(X_test_s)
    print(f"Severity Model Accuracy: {accuracy_score(y_test_s, y_pred_s):.4f}")
    print(classification_report(y_test_s, y_pred_s, target_names=le_sev.classes_))

    # Save models and encoders
    print("\nSaving models and encoders...")
    joblib.dump(rf_cat, os.path.join(MODEL_DIR, "rf_category_model.joblib"))
    joblib.dump(le_cat, os.path.join(MODEL_DIR, "le_category.joblib"))
    joblib.dump(rf_sev, os.path.join(MODEL_DIR, "rf_severity_model.joblib"))
    joblib.dump(le_sev, os.path.join(MODEL_DIR, "le_severity.joblib"))
    print("Training complete and models saved successfully!")

if __name__ == "__main__":
    train()
