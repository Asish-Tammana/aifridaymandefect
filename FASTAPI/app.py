"""
app.py

Minimal MES API: one FastAPI app, one SQLite table ("events"), one
background loop that calls generator.generate_tick() every 30s and
stores the results. That's the whole system.

Run:
    uvicorn app:app --reload
Docs:
    http://localhost:8000/docs
"""

import asyncio
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, desc
)
from sqlalchemy.orm import sessionmaker, declarative_base, Session

import generator
#import data

TICK_SECONDS = 30

# --- DB setup -----------------------------------------------------------

engine = create_engine("sqlite:///./mes.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Event(Base):
    __tablename__ = "liveupdate_stream"

    event_id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, default=datetime.utcnow)
    machine_id = Column(String, index=True)
    equipment_type = Column(String)
    temperature = Column(Float)
    vibration = Column(Float)
    humidity = Column(Float)
    pressure = Column(Float)
    rotations_per_minute = Column(Float)
    failure_code = Column(String, nullable=True)
    failure_category = Column(String, nullable=True)
    severity = Column(String, nullable=True)


Base.metadata.create_all(bind=engine)


# --- Pydantic response schema --------------------------------------------

class EventOut(BaseModel):
    event_id: int
    timestamp: datetime
    machine_id: str
    equipment_type: str
    temperature: float
    vibration: float
    humidity: float
    pressure: float
    rotations_per_minute: float
    failure_code: Optional[str] = None
    failure_category: Optional[str] = None
    severity: Optional[str] = None

    class Config:
        from_attributes = True


# --- storage helper --------------------------------------------------------

def store_tick():
    db: Session = SessionLocal()
    try:
        events = generator.generate_tick()
        for event_dict in events:
            db.add(Event(**event_dict))
        db.commit()
        print(f"[store_tick] inserted {len(events)} events at {datetime.utcnow().isoformat()}")
    except Exception:
        db.rollback()
        print("[store_tick] FAILED to insert:")
        traceback.print_exc()
        raise
    finally:
        db.close()


# --- background scheduler --------------------------------------------------

async def scheduler_loop():
    while True:
        try:
            store_tick()
        except Exception:
            print("[scheduler] tick failed:")
            traceback.print_exc()
        await asyncio.sleep(TICK_SECONDS)


_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _task
    print("[startup] creating tables + running first tick...")
    Base.metadata.create_all(bind=engine)  # safe to call again; also confirms engine/table are OK
    try:
        store_tick()  # generate one immediately so endpoints aren't empty on first hit
    except Exception:
        print("[startup] initial store_tick() failed -- see traceback above. "
              "The app will still start, but the background loop will likely fail too.")
    _task = asyncio.create_task(scheduler_loop())
    yield
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Mock MES API", version="1.0.0", lifespan=lifespan)


# --- endpoints ---------------------------------------------------------

@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Mock MES API is running.",
        "docs": "/docs",
        "endpoints": ["/machines", "/events/latest", "/events/{machine_id}", "/events"],
    }


@app.get("/debug", tags=["Root"])
def debug():
    """Quick sanity check: how many rows are actually in the DB, and where the file lives."""
    import os
    db = SessionLocal()
    try:
        count = db.query(Event).count()
        return {
            "db_file": os.path.abspath("mes.db"),
            "db_file_exists": os.path.exists("mes.db"),
            "total_events_in_table": count,
        }
    finally:
        db.close()


@app.get("/machines", tags=["MES"])
def list_machines():
    """List known machine_id -> equipment_type pairs."""
    return [{"machine_id": mid, "equipment_type": etype} for mid, etype in generator.MACHINES.items()]


@app.get("/events/latest", response_model=List[EventOut], tags=["MES"])
def latest_events():
    """Latest event for every machine (live snapshot)."""
    db = SessionLocal()
    try:
        results = []
        for machine_id in generator.MACHINES:
            row = (
                db.query(Event)
                .filter(Event.machine_id == machine_id)
                .order_by(desc(Event.timestamp))
                .first()
            )
            if row:
                results.append(row)
        return results
    finally:
        db.close()


@app.get("/events/{machine_id}", response_model=List[EventOut], tags=["MES"])
def machine_history(machine_id: str, limit: int = Query(100, ge=1, le=2000)):
    """Historical events for one machine, most recent first."""
    if machine_id not in generator.MACHINES:
        raise HTTPException(status_code=404, detail=f"Unknown machine_id '{machine_id}'")
    db = SessionLocal()
    try:
        return (
            db.query(Event)
            .filter(Event.machine_id == machine_id)
            .order_by(desc(Event.timestamp))
            .limit(limit)
            .all()
        )
    finally:
        db.close()


@app.get("/events", response_model=List[EventOut], tags=["MES"])
def all_events(limit: int = Query(200, ge=1, le=5000)):
    """All events across every machine, most recent first. Optional severity filter."""
    db = SessionLocal()
    try:
        return (
            db.query(Event)
            .order_by(desc(Event.timestamp), desc(Event.event_id))
            .limit(limit)
            .all()
        )
    finally:
        db.close()
@app.get("/latest-20-machines", response_model=List[EventOut], tags=["MES"])
def latest_20_machines():
    """
    Returns the latest 20 event records across all machines,
    ordered from newest to oldest.
    """
    db = SessionLocal()
    try:
        events = (
            db.query(Event)
            .order_by(desc(Event.timestamp), desc(Event.event_id))
            .limit(20)
            .all()
        )
        return events
    finally:
        db.close()
