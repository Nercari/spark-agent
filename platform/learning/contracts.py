"""Core data contracts for Gemini Spark Autonomous Learning Platform (Hermes-Compatible Baseline)."""

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    USER_AUTHORIZED_INSTRUCTION = "USER_AUTHORIZED_INSTRUCTION"
    USER_CORRECTION = "USER_CORRECTION"
    TOOL_RESULT = "TOOL_RESULT"
    EXTERNAL_CONTENT = "EXTERNAL_CONTENT"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"


class TrustClass(str, Enum):
    TRUSTED_USER_AUTHORITY = "TRUSTED_USER_AUTHORITY"
    INTERNAL_EXECUTION = "INTERNAL_EXECUTION"
    UNTRUSTED_EXTERNAL_EVIDENCE = "UNTRUSTED_EXTERNAL_EVIDENCE"
    VERIFICATION = "VERIFICATION"


class PayloadOrigin(str, Enum):
    LOCAL_COMPUTATION = "LOCAL_COMPUTATION"
    EXTERNAL_WEB = "EXTERNAL_WEB"
    EMAIL = "EMAIL"
    DOCUMENT = "DOCUMENT"
    MCP = "MCP"
    CONNECTED_APP = "CONNECTED_APP"
    UNKNOWN_EXTERNAL = "UNKNOWN_EXTERNAL"


class VerificationStatus(str, Enum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class MutationDecision(str, Enum):
    AUTO_COMMIT = "AUTO_COMMIT"
    REJECT_STALE = "REJECT_STALE"
    BLOCKED_PERMISSION = "BLOCKED_PERMISSION"
    BLOCKED_UNTRUSTED = "BLOCKED_UNTRUSTED"
    REJECT_SYSTEM_SKILL = "REJECT_SYSTEM_SKILL"
    NO_LEARNING = "NO_LEARNING"


def generate_sha256(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


@dataclass
class EvidenceEvent:
    id: str
    timestamp: str
    event_type: EventType
    trust_class: TrustClass
    content: str
    payload_origin: PayloadOrigin = PayloadOrigin.LOCAL_COMPUTATION
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["trust_class"] = self.trust_class.value
        d["payload_origin"] = self.payload_origin.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceEvent":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            event_type=EventType(data["event_type"]),
            trust_class=TrustClass(data["trust_class"]),
            content=data["content"],
            payload_origin=PayloadOrigin(data.get("payload_origin", PayloadOrigin.LOCAL_COMPUTATION.value)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class VerificationResult:
    status: VerificationStatus
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        return cls(
            status=VerificationStatus(data["status"]),
            reason=data["reason"],
            details=data.get("details", {}),
        )


@dataclass
class TaskRun:
    id: str
    goal: str
    started_at: str
    completed_at: str
    user_scope_id: str
    project_scope_id: str
    skill_name: str
    skill_version: str
    evidence_events: List[EvidenceEvent] = field(default_factory=list)
    final_output: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    verification_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verification_status"] = self.verification_status.value
        d["evidence_events"] = [e.to_dict() for e in self.evidence_events]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRun":
        events = [EvidenceEvent.from_dict(e) for e in data.get("evidence_events", [])]
        return cls(
            id=data["id"],
            goal=data["goal"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            user_scope_id=data["user_scope_id"],
            project_scope_id=data["project_scope_id"],
            skill_name=data["skill_name"],
            skill_version=data["skill_version"],
            evidence_events=events,
            final_output=data.get("final_output", ""),
            verification_status=VerificationStatus(data.get("verification_status", VerificationStatus.UNKNOWN.value)),
            verification_details=data.get("verification_details", {}),
        )


@dataclass
class SkillVersion:
    version_id: str
    skill_name: str
    parent_version_id: Optional[str]
    content: str
    content_hash: str
    created_at: str
    created_from_task_run_id: Optional[str] = None
    change_reason: str = ""
    diff: Optional[str] = None
    status: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillVersion":
        return cls(**data)


@dataclass
class LearningMutation:
    id: str
    task_run_id: str
    operation: str
    target_skill: str
    base_version_id: str
    base_version_hash: str
    proposed_content: str
    diff: str
    reason: str
    decision: MutationDecision
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    committed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningMutation":
        d = data.copy()
        d["decision"] = MutationDecision(d["decision"])
        return cls(**d)
