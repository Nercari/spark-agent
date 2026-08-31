from __future__ import annotations
import sqlite3
import json
import time
import os
from typing import List, Optional, Dict, Any
from platform.curator.contracts import TelemetryEvent, TelemetryReport

class CuratorTelemetry:
    """SQLite-backed telemetry tracker for curator runs, regressions, and metric trends."""

    def __init__(self, db_path: str = ".learning/curator_telemetry.sqlite3"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    skill_name TEXT,
                    timestamp REAL NOT NULL,
                    payload JSON NOT NULL
                )
            """)
            conn.commit()

    def record_event(self, event: TelemetryEvent) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO telemetry_events (id, event_type, skill_name, timestamp, payload) VALUES (?, ?, ?, ?, ?)",
                (event.event_id, event.event_type, event.skill_name, event.timestamp, json.dumps(event.payload))
            )
            conn.commit()

    def get_events_for_skill(self, skill_name: str) -> List[TelemetryEvent]:
        events = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, event_type, skill_name, timestamp, payload FROM telemetry_events WHERE skill_name = ? ORDER BY timestamp ASC",
                (skill_name,)
            )
            for row in cursor.fetchall():
                events.append(TelemetryEvent(
                    event_id=row[0],
                    event_type=row[1],
                    skill_name=row[2],
                    timestamp=row[3],
                    payload=json.loads(row[4])
                ))
        return events

    def generate_report(self) -> TelemetryReport:
        total_events = 0
        skill_counts: Dict[str, int] = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT skill_name, COUNT(*) FROM telemetry_events GROUP BY skill_name")
            for row in cursor.fetchall():
                name = row[0] or "system"
                cnt = row[1]
                skill_counts[name] = cnt
                total_events += cnt

        return TelemetryReport(
            total_events=total_events,
            events_by_skill=skill_counts,
            timestamp=time.time()
        )
