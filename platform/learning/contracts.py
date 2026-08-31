"""Domain contracts, data structures, and schemas for Autonomous Learning Platform."""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def generate_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class VerificationStatus(str, Enum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class MutationDecision(str, Enum):
    AUTO_COMMIT = "AUTO_COMMIT"
    REJECT = "REJECT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class PayloadOrigin(str, Enum):
    INTERNAL = "INTERNAL"
    MCP = "MCP"
    USER_PROMPT = "USER_PROMPT"
    EXTERNAL_DATA = "EXTERNAL_DATA"


@dataclass
class EvidenceRecord:
    evidence_id: str
    tool_name: str
    params: Dict[str, Any]
    result: Dict[str, Any]
    payload_origin: PayloadOrigin
    is_error: bool = False
    is_recovery: bool = False
    operation_id: Optional[str] = None
    attempt_id: int = 1
    parent_attempt_id: Optional[str] = None
    diff_summary: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["payload_origin"] = self.payload_origin.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceRecord":
        d = data.copy()
        d["payload_origin"] = PayloadOrigin(d["payload_origin"])
        return cls(**d)


@dataclass
class TaskRunSummary:
    task_run_id: str
    project_scope_id: Optional[str]
    skill_name: str
    skill_version: str
    goal: str
    verification_status: VerificationStatus
    has_recovery: bool
    timestamp: str
    summary_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verification_status"] = self.verification_status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRunSummary":
        d = data.copy()
        d["verification_status"] = VerificationStatus(d["verification_status"])
        return cls(**d)


@dataclass
class TaskRun:
    id: str
    goal: str
    skill_name: str
    skill_version: str
    evidence_records: List[EvidenceRecord] = field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    verification_reason: str = ""
    user_instructions: List[str] = field(default_factory=list)
    user_corrections: List[str] = field(default_factory=list)
    output: Optional[str] = None
    project_scope_id: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

    def has_recovery(self) -> bool:
        return any(e.is_recovery for e in self.evidence_records)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verification_status"] = self.verification_status.value
        d["evidence_records"] = [e.to_dict() for e in self.evidence_records]
        return d

    def to_summary(self) -> TaskRunSummary:
        return TaskRunSummary(
            task_run_id=self.id,
            project_scope_id=self.project_scope_id,
            skill_name=self.skill_name,
            skill_version=self.skill_version,
            goal=self.goal,
            verification_status=self.verification_status,
            has_recovery=self.has_recovery(),
            timestamp=self.completed_at or self.started_at,
            summary_text=f"TaskRun {self.id}: goal='{self.goal}', status={self.verification_status.value}, recovery={self.has_recovery()}",
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRun":
        d = data.copy()
        d["verification_status"] = VerificationStatus(d["verification_status"])
        d["evidence_records"] = [EvidenceRecord.from_dict(e) for e in d.get("evidence_records", [])]
        return cls(**d)


@dataclass
class SkillVersionMetadata:
    version_id: str
    parent_version_id: Optional[str]
    created_at: str
    content_hash: str
    author: str
    change_reason: str
    task_run_id: Optional[str] = None
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0
    unified_diff: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillVersionMetadata":
        return cls(**data)


@dataclass
class LearningMutationProposal:
    skill_name: str
    base_version_id: str
    proposed_content: str
    change_reason: str
    decision: MutationDecision
    task_run_id: str
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0
    rationale: str = ""
    unified_diff: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        return d
