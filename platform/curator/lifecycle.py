from __future__ import annotations
import time
from typing import Optional, List, Dict, Any
from platform.curator.contracts import TelemetryEvent
from platform.curator.telemetry import CuratorTelemetry

class CuratorLifecycleObserver:
    """Observes task execution lifecycle events and logs structured telemetry."""

    def __init__(self, telemetry: CuratorTelemetry):
        self.telemetry = telemetry

    def on_task_start(self, task_id: str, skill_name: str, goal: str) -> None:
        self.telemetry.record_event(TelemetryEvent(
            event_id=f"start_{task_id}",
            event_type="TASK_START",
            skill_name=skill_name,
            timestamp=time.time(),
            payload={"task_id": task_id, "goal": goal}
        ))

    def on_task_complete(
        self,
        task_id: str,
        skill_name: str,
        verification_status: str,
        had_recovery: bool,
        duration_ms: float,
    ) -> None:
        self.telemetry.record_event(TelemetryEvent(
            event_id=f"end_{task_id}",
            event_type="TASK_COMPLETE",
            skill_name=skill_name,
            timestamp=time.time(),
            payload={
                "task_id": task_id,
                "verification_status": verification_status,
                "had_recovery": had_recovery,
                "duration_ms": duration_ms,
            }
        ))

    def on_attributable_regression(
        self,
        task_id: str,
        skill_name: str,
        current_version: str,
        previous_stable_version: str,
        regression_details: str,
    ) -> None:
        self.telemetry.record_event(TelemetryEvent(
            event_id=f"regr_{task_id}",
            event_type="ATTRIBUTABLE_REGRESSION",
            skill_name=skill_name,
            timestamp=time.time(),
            payload={
                "task_id": task_id,
                "current_version": current_version,
                "previous_stable_version": previous_stable_version,
                "details": regression_details,
            }
        ))
