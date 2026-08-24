"""Evidence Recorder for TaskRuns and EvidenceEvents."""

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from platform.learning.contracts import (
    TaskRun,
    EvidenceEvent,
    EventType,
    TrustClass,
    VerificationStatus,
)


class EvidenceRecorder:
    def __init__(
        self,
        task_id: Optional[str] = None,
        goal: str = "",
        skill_name: str = "",
        skill_version: str = "v1",
        user_scope_id: str = "default_user",
        project_scope_id: str = "default_project",
        storage_dir: Optional[str] = None,
    ):
        self.task_run_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        self.goal = goal
        self.skill_name = skill_name
        self.skill_version = skill_version
        self.user_scope_id = user_scope_id
        self.project_scope_id = project_scope_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.events: List[EvidenceEvent] = []
        self.final_output = ""
        self.verification_status = VerificationStatus.UNKNOWN
        self.verification_details: Dict[str, Any] = {}
        self.storage_dir = storage_dir or "/working_dir/c_b490a8c7dd21c813/.learning/evidence"
        os.makedirs(self.storage_dir, exist_ok=True)

    def _add_event(
        self,
        event_type: EventType,
        trust_class: TrustClass,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvidenceEvent:
        event = EvidenceEvent(
            id=f"ev_{len(self.events) + 1}_{uuid.uuid4().hex[:6]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            trust_class=trust_class,
            content=content,
            metadata=metadata or {},
        )
        self.events.append(event)
        return event

    def record_user_instruction(self, instruction: str) -> EvidenceEvent:
        return self._add_event(
            event_type=EventType.USER_AUTHORIZED_INSTRUCTION,
            trust_class=TrustClass.TRUSTED_USER_AUTHORITY,
            content=instruction,
        )

    def record_user_correction(self, correction: str) -> EvidenceEvent:
        return self._add_event(
            event_type=EventType.USER_CORRECTION,
            trust_class=TrustClass.TRUSTED_USER_AUTHORITY,
            content=correction,
        )

    def record_tool_result(
        self, tool_name: str, params: Dict[str, Any], result: Any, is_error: bool = False, is_transient: bool = False
    ) -> EvidenceEvent:
        return self._add_event(
            event_type=EventType.TOOL_RESULT,
            trust_class=TrustClass.INTERNAL_EXECUTION,
            content=json.dumps({"tool": tool_name, "params": params, "result": result}),
            metadata={"tool_name": tool_name, "is_error": is_error, "is_transient": is_transient},
        )

    def record_external_content(self, source_ref: str, content: str) -> EvidenceEvent:
        """Records external content. Strictly labeled UNTRUSTED_EXTERNAL_EVIDENCE."""
        return self._add_event(
            event_type=EventType.EXTERNAL_CONTENT,
            trust_class=TrustClass.UNTRUSTED_EXTERNAL_EVIDENCE,
            content=content,
            metadata={"source_ref": source_ref},
        )

    def record_model_inference(self, thought_or_output: str) -> EvidenceEvent:
        return self._add_event(
            event_type=EventType.MODEL_INFERENCE,
            trust_class=TrustClass.INTERNAL_EXECUTION,
            content=thought_or_output,
        )

    def record_verification(
        self, status: VerificationStatus, reason: str, details: Optional[Dict[str, Any]] = None
    ) -> EvidenceEvent:
        self.verification_status = status
        self.verification_details = details or {"reason": reason}
        return self._add_event(
            event_type=EventType.VERIFICATION_RESULT,
            trust_class=TrustClass.VERIFICATION,
            content=json.dumps({"status": status.value, "reason": reason, "details": details or {}}),
            metadata={"status": status.value},
        )

    def complete_task(self, final_output: str) -> TaskRun:
        self.final_output = final_output
        completed_at = datetime.now(timezone.utc).isoformat()
        task_run = TaskRun(
            id=self.task_run_id,
            goal=self.goal,
            started_at=self.started_at,
            completed_at=completed_at,
            user_scope_id=self.user_scope_id,
            project_scope_id=self.project_scope_id,
            skill_name=self.skill_name,
            skill_version=self.skill_version,
            evidence_events=self.events,
            final_output=self.final_output,
            verification_status=self.verification_status,
            verification_details=self.verification_details,
        )
        self.save_task_run(task_run)
        return task_run

    def save_task_run(self, task_run: TaskRun) -> str:
        filepath = os.path.join(self.storage_dir, f"{task_run.id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(task_run.to_dict(), f, indent=2)
        return filepath
