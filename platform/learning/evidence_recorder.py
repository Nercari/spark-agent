"""Evidence Recorder for TaskRuns and EvidenceEvents with Operational Payload Provenance and Unique Operation Identity."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from platform.learning.contracts import (
    EvidenceEvent,
    EventType,
    TrustClass,
    PayloadOrigin,
    TaskRun,
    VerificationStatus,
)


class EvidenceRecorder:
    """Records chronological, typed evidence events during a single task run."""

    def __init__(
        self,
        task_id: str,
        goal: str,
        skill_name: str,
        skill_version: str,
        storage_dir: Optional[str] = None,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
    ):
        self.task_id = task_id
        self.goal = goal
        self.skill_name = skill_name
        self.skill_version = skill_version
        self.storage_dir = storage_dir
        self.project_scope_id = project_scope_id or "default_project"
        self.user_scope_id = user_scope_id or "default_user"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.events: List[EvidenceEvent] = []
        self.verification_status = VerificationStatus.UNKNOWN
        self.verification_details: Dict[str, Any] = {}

    def _create_event_id(self) -> str:
        return f"ev_{uuid.uuid4().hex[:10]}"

    def record_tool_result(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        payload_origin: PayloadOrigin = PayloadOrigin.MCP,
        is_error: bool = False,
        is_recovery: bool = False,
        operation_id: Optional[str] = None,
        attempt_id: int = 1,
        parent_attempt_id: Optional[str] = None,
        diff_summary: Optional[str] = None,
    ) -> EvidenceEvent:
        event = EvidenceEvent(
            id=self._create_event_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=EventType.TOOL_RESULT,
            trust_class=TrustClass.INTERNAL_EXECUTION if not is_error else TrustClass.UNTRUSTED_EXTERNAL_EVIDENCE,
            content=json.dumps({"tool": tool_name, "params": params, "result": result}),
            payload_origin=payload_origin,
            operation_id=operation_id or f"op_{tool_name}",
            attempt_id=attempt_id,
            parent_attempt_id=parent_attempt_id,
            metadata={"is_error": is_error, "is_recovery": is_recovery, "diff_summary": diff_summary},
        )
        self.events.append(event)
        return event

    def record_user_instruction(self, instruction: str) -> EvidenceEvent:
        event = EvidenceEvent(
            id=self._create_event_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=EventType.USER_AUTHORIZED_INSTRUCTION,
            trust_class=TrustClass.TRUSTED_USER_AUTHORITY,
            content=instruction,
            payload_origin=PayloadOrigin.LOCAL_COMPUTATION,
        )
        self.events.append(event)
        return event

    def record_user_correction(self, correction: str) -> EvidenceEvent:
        event = EvidenceEvent(
            id=self._create_event_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=EventType.USER_CORRECTION,
            trust_class=TrustClass.TRUSTED_USER_AUTHORITY,
            content=correction,
            payload_origin=PayloadOrigin.LOCAL_COMPUTATION,
        )
        self.events.append(event)
        return event

    def record_verification(self, status: VerificationStatus, reason: str, details: Optional[Dict[str, Any]] = None) -> EvidenceEvent:
        self.verification_status = status
        self.verification_details = details or {"reason": reason}
        event = EvidenceEvent(
            id=self._create_event_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=EventType.VERIFICATION_RESULT,
            trust_class=TrustClass.VERIFICATION,
            content=json.dumps({"status": status.value, "reason": reason, "details": self.verification_details}),
            payload_origin=PayloadOrigin.LOCAL_COMPUTATION,
        )
        self.events.append(event)
        return event

    def complete_task(self, output: str) -> TaskRun:
        return TaskRun(
            id=self.task_id,
            goal=self.goal,
            started_at=self.started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            user_scope_id=self.user_scope_id,
            project_scope_id=self.project_scope_id,
            skill_name=self.skill_name,
            skill_version=self.skill_version,
            evidence_events=self.events,
            final_output=output,
            verification_status=self.verification_status,
            verification_details=self.verification_details,
        )
