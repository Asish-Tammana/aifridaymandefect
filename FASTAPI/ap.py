"""
FastAPI service that:
  1. Accepts a sensor event for a machine_id (temperature, vibration, humidity,
     pressure, rotations_per_minute, failure_category, severity, confidence).
  2. Sends the event + the machine's current schedule to an LLM, which decides
     whether next_service_date should move EARLIER, LATER, or stay the same,
     and gives a reason.
  3. If it changes, updates machine_status and looks up technician(s)
     qualified for that machine's equipment_type (JOIN on equipment_type).
  4. Logs the event + decision + reasoning into the events table.

Run:
    pip install -r requirements.txt
    cp .env.example .env      # fill in OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
    export $(cat .env | xargs)
    uvicorn api:app --reload
"""
import os
import sqlite3
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, List

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

DB_PATH = "mes.db"
#"cmm.db"

# ============================================================
# LLM client config (internal proxy / self-signed endpoint)
# ============================================================
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://genailab.tcs.in")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "genailab-maas-gpt-5.2")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-yj4dfAYczIX7q70FwdRtyQ")

# Internal/self-signed endpoints often need SSL verification disabled
http_client = httpx.Client(verify=False)

llm_client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    http_client=http_client,
)

app = FastAPI(title="CMM Predictive Maintenance API")


# ============================================================
# Reference thresholds — passed to the LLM as context, not used
# to decide anything directly. The LLM makes the final call.
# ============================================================
THRESHOLDS = {
    "temperature": {"warning": 200.0, "critical": 280.0},
    "vibration":   {"warning": 2.0,   "critical": 3.5},
    "pressure":    {"warning": 200.0, "critical": 260.0},
    "humidity":    {"warning": 70.0,  "critical": 78.0},
}


# ============================================================
# Request/response models
# ============================================================
class SensorEvent(BaseModel):
    event_id: Optional[str] = None
    timestamp: Optional[str] = None
    machine_id: str
    equipement_type: Optional[str] = None  # optional; looked up from DB if omitted
    temperature: float
    vibration: float
    humidity: float
    pressure: float
    rotations_per_minute: float
    failure_category: Optional[str] = "None"
    severity: Optional[str] = ""
    confidence: Optional[float] = 0.0


class TechnicianOut(BaseModel):
    technician_id: str
    technician_name: str
    technician_phone_number: str
    equipment_type: str


class EvaluationResult(BaseModel):
    machine_id: str
    equipment_type: str
    decision: str                 # 'advance' | 'delay' | 'no_change'
    risk_level: str
    reasoning: str
    previous_next_service_date: str
    new_next_service_date: str
    date_shift_days: int
    technicians: List[TechnicianOut] = []


# ============================================================
# DB helpers
# ============================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_machine(conn, machine_id: str):
    row = conn.execute(
        "SELECT * FROM machine_status WHERE machine_id = ?", (machine_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"machine_id '{machine_id}' not found")
    return dict(row)


def get_technicians(conn, equipment_type: str) -> List[dict]:
    rows = conn.execute(
        "SELECT * FROM technician WHERE equipment_type = ?", (equipment_type,)
    ).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# LLM decision logic
# ============================================================
def build_prompt(machine: dict, event: SensorEvent) -> str:
    return f"""You are a predictive-maintenance assistant for industrial machines.
You decide whether a machine's next scheduled service date should move EARLIER,
move LATER, or stay the same, based on a live sensor reading.

Machine (current record):
- machine_id: {machine['machine_id']}
- machine_name: {machine['machine_name']}
- equipment_type: {machine['equipment_type']}
- status: {machine['status']}
- last_service_date: {machine['last_service_date']}
- current next_service_date (the plan): {machine['next_service_date']}
- standard_service_interval_days: {machine['standard_service_interval_days']}
- days_since_last_service: {machine['days_since_last_service']}
- expected_usage_hours: {machine['expected_usage_hours']}
- actual_usage_hours: {machine['actual_usage_hours']}
- today's date: {datetime.now().strftime('%Y-%m-%d')}

Latest sensor event:
- event_id: {event.event_id}
- timestamp: {event.timestamp}
- temperature: {event.temperature}
- vibration: {event.vibration}
- humidity: {event.humidity}
- pressure: {event.pressure}
- rotations_per_minute: {event.rotations_per_minute}
- failure_category: {event.failure_category}
- severity: {event.severity}
- confidence: {event.confidence}

Reference thresholds (for context only — use your judgment, not just these):
- temperature: warning >= {THRESHOLDS['temperature']['warning']}, critical >= {THRESHOLDS['temperature']['critical']}
- vibration: warning >= {THRESHOLDS['vibration']['warning']}, critical >= {THRESHOLDS['vibration']['critical']}
- pressure: warning >= {THRESHOLDS['pressure']['warning']}, critical >= {THRESHOLDS['pressure']['critical']}
- humidity: warning >= {THRESHOLDS['humidity']['warning']}, critical >= {THRESHOLDS['humidity']['critical']}

Task:
- If the readings, severity, or failure_category indicate elevated risk of failure,
  move next_service_date EARLIER (sooner) than the current plan. The more severe/
  confident the signal, the larger the pull-forward (in days).
- If everything is well within normal range and there is no failure signal,
  you may move next_service_date LATER (a modest push-out is fine).
- If signals are mixed or inconclusive, keep next_service_date unchanged.
- Never set next_service_date to a date before today.
- Do not move the date by more than {machine['standard_service_interval_days']} days
  in either direction.

Respond with ONLY valid JSON, no markdown, no extra text, in exactly this shape:
{{"decision": "advance" | "delay" | "no_change", "new_next_service_date": "YYYY-MM-DD", "risk_level": "<low|moderate|high|critical>", "reasoning": "<one or two short sentences>"}}
"""


def call_llm_for_decision(machine: dict, event: SensorEvent) -> dict:
    prompt = build_prompt(machine, event)
    response = llm_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail=f"LLM returned invalid JSON: {content}")

    for key in ("decision", "new_next_service_date", "risk_level", "reasoning"):
        if key not in parsed:
            raise HTTPException(status_code=502, detail=f"LLM response missing '{key}': {parsed}")

    if parsed["decision"] not in ("advance", "delay", "no_change"):
        raise HTTPException(
            status_code=502,
            detail=f"LLM returned invalid decision '{parsed['decision']}'",
        )

    return parsed


# ============================================================
# Endpoint
# ============================================================
@app.post("/machines/{machine_id}/evaluate", response_model=EvaluationResult)
def evaluate_machine(machine_id: str, event: SensorEvent):
    if event.machine_id != machine_id:
        raise HTTPException(
            status_code=400,
            detail="machine_id in path and body must match",
        )

    conn = get_conn()
    try:
        machine = get_machine(conn, machine_id)
        equipment_type = machine["equipment_type"]
        previous_next = machine["next_service_date"]
        today = datetime.now().date()

        result = call_llm_for_decision(machine, event)
        decision = result["decision"]
        risk_level = result["risk_level"]
        reasoning = result["reasoning"]

        if decision == "no_change":
            new_next = previous_next
            date_shift_days = 0
            technicians = []
        else:
            # validate/clamp the LLM's date
            try:
                candidate = datetime.strptime(result["new_next_service_date"], "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM returned invalid date: {result['new_next_service_date']}",
                )
            if candidate < today:
                candidate = today  # safety net: never schedule in the past

            new_next = candidate.strftime("%Y-%m-%d")
            prev_dt = datetime.strptime(previous_next, "%Y-%m-%d").date()
            date_shift_days = abs((candidate - prev_dt).days)

            conn.execute(
                "UPDATE machine_status SET next_service_date = ?, last_updated = ? WHERE machine_id = ?",
                (new_next, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), machine_id),
            )

            # only surface technicians when the date actually changed
            technicians = get_technicians(conn, equipment_type)

        # ---- log the event regardless of outcome ----
        event_id = event.event_id or f"EVT-{uuid.uuid4().hex[:8].upper()}"
        timestamp = event.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """INSERT OR REPLACE INTO events
               (event_id, timestamp, machine_id, equipment_type, temperature, vibration,
                humidity, pressure, rotations_per_minute, failure_category, severity,
                confidence, risk_score, decision, date_shift_days,
                previous_next_service_date, new_next_service_date, reasoning)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event_id, timestamp, machine_id, equipment_type,
                event.temperature, event.vibration, event.humidity, event.pressure,
                event.rotations_per_minute, event.failure_category, event.severity,
                event.confidence, None, decision, date_shift_days,
                previous_next, new_next, reasoning,
            ),
        )
        conn.commit()

        return EvaluationResult(
            machine_id=machine_id,
            equipment_type=equipment_type,
            decision=decision,
            risk_level=risk_level,
            reasoning=reasoning,
            previous_next_service_date=previous_next,
            new_next_service_date=new_next,
            date_shift_days=date_shift_days,
            technicians=[TechnicianOut(**t) for t in technicians],
        )
    finally:
        conn.close()


@app.get("/health/llm")
def check_llm_connection():
    """
    Lightweight connectivity check — sends a trivial prompt to the LLM
    and reports whether the call succeeded, without touching the DB
    or requiring a valid machine_id.
    """
    try:
        response = llm_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": "Reply with only the word: OK"}],
        )
        content = response.choices[0].message.content
        return {
            "status": "ok",
            "base_url": OPENAI_BASE_URL,
            "model": OPENAI_MODEL,
            "llm_reply": content,
        }
    except Exception as e:
        return {
            "status": "error",
            "base_url": OPENAI_BASE_URL,
            "model": OPENAI_MODEL,
            "error": str(e),
        }


@app.get("/machines/{machine_id}/events")
def get_machine_events(machine_id: str):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM events WHERE machine_id = ? ORDER BY timestamp DESC",
            (machine_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()