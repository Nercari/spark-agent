from __future__ import annotations
import json
import os
import time
from typing import Optional, Dict, Any, List
from platform.learning.contracts import EvidenceEvent, TaskExecutionRecord

class EvidenceRecorder:
    """Captures granular execution events and persists execution audit trails."""

    def __init__(self, storage_dir: str = ".learning/evidence"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def record_event(
        self,
        task_id: str,
        event_type: str,
        payload: Dict[str, Any],
        skill_name: Optional[str] = None,
        skill_version: Optional[str] = None,
    ) -> EvidenceEvent:
        event = EvidenceEvent(
            event_id=f"ev_{int(time.time()*1000)}_{len(payload)}",
            task_id=task_id,
            event_type=event_type,
            timestamp=time.time(),
            skill_name=skill_name,
            skill_version=skill_version,
            payload=payload,
        )
        return event

    def save_task_record(self, record: TaskExecutionRecord) -> None:
        file_path = os.path.join(self.storage_dir, f"{record.task_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)
