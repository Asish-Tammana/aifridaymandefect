"""
seed_bulk.py

Run this ONCE, before starting the API, to backfill the `events` table
with historical training data.

It reuses the exact same simulation logic as the live API
(generator.py) so the historical data and the live data the API keeps
generating afterward are statistically consistent -- same machines,
same drift behavior, same anomaly correlations.

Usage:
    python seed_bulk.py                  # 50,000 records, default spacing
    python seed_bulk.py --records 100000
    python seed_bulk.py --interval 60    # seconds between ticks

After this finishes, start the API as usual:
    uvicorn app:app --reload

The API will keep appending new rows starting from "now" -- it doesn't
know or care that the earlier rows were seeded in bulk, since it's the
same table, same schema, same generator.
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

import generator

DB_FILE = "./mes.db"
DEFAULT_RECORDS = 50_000
DEFAULT_INTERVAL_SECONDS = 30  # matches TICK_SECONDS in app.py, keeps spacing consistent
BATCH_SIZE = 1000              # commit in batches instead of one giant transaction

# --- DB setup (must match app.py exactly -- same table, same columns) ------

engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Event(Base):
    __tablename__ = "events"

    event_id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True)
    machine_id = Column(String, index=True)
    equipment_type = Column(String)
    temperature = Column(Float)
    vibration = Column(Float)
    humidity = Column(Float)
    pressure = Column(Float)
    rotations_per_minute = Column(Float)
    failure_code = Column(String, nullable=True)
    failure_category = Column(String, nullable=True)
    severity = Column(String)


def seed(total_records: int, interval_seconds: int):
    Base.metadata.create_all(bind=engine)

    machines = list(generator.MACHINES.items())          # [(machine_id, equipment_type), ...]
    ticks_needed = -(-total_records // len(machines))     # ceil division: one event per machine per tick
    actual_total = ticks_needed * len(machines)

    span = timedelta(seconds=interval_seconds * ticks_needed)
    start_time = datetime.now(timezone.utc) - span

    print(f"Seeding {actual_total:,} records "
          f"({ticks_needed:,} ticks x {len(machines)} machines, "
          f"{interval_seconds}s apart)")
    print(f"Historical range: {start_time.isoformat()}  ->  now")

    db = SessionLocal()
    batch = []
    inserted = 0
    t0 = time.time()

    try:
        for tick in range(ticks_needed):
            tick_time = start_time + timedelta(seconds=interval_seconds * tick)
            for machine_id, equipment_type in machines:
                event = generator.generate_event(machine_id, equipment_type)
                event["timestamp"] = tick_time  # override "now" with the historical slot
                batch.append(event)

            if len(batch) >= BATCH_SIZE:
                db.bulk_insert_mappings(Event, batch)
                db.commit()
                inserted += len(batch)
                batch = []
                print(f"  ...{inserted:,} / {actual_total:,} inserted", end="\r")

        if batch:
            db.bulk_insert_mappings(Event, batch)
            db.commit()
            inserted += len(batch)

        elapsed = time.time() - t0
        print(f"\nDone. Inserted {inserted:,} records in {elapsed:.1f}s.")

        total_in_table = db.query(Event).count()
        print(f"Total rows now in 'events' table: {total_in_table:,}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk-seed historical MES events for model training.")
    parser.add_argument("--records", type=int, default=DEFAULT_RECORDS,
                         help=f"Approximate number of records to insert (default {DEFAULT_RECORDS:,}).")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS,
                         help=f"Seconds between simulated ticks (default {DEFAULT_INTERVAL_SECONDS}).")
    args = parser.parse_args()

    seed(args.records, args.interval)
