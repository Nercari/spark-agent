"""Data contracts for Autonomous Learning Curator, Lifecycle Telemetry, Rollback Protocols & Action Audit."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from platform.learning.contracts import VerificationStatus
from platform.memory.contracts import MemoryScope


class ArtifactType(str, Enum):
    SKILL = "SKILL"
    MEMORY = "MEMORY"


class ObservedEffect(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    UNKNOWN = "UNKNOWN"


class CuratorDecision(str, Enum):
    NO_ACTION = "NO_ACTION"
    KEEP = "KEEP"
    MARK_STALE = "MARK_STALE"
    COMPACT_SKILL = "COMPACT_SKILL"
    RETIRE_SKILL_VERSION = "RETIRE_SKILL_VERSION"
    ARCHIVE_MEMORY = "ARCHIVE_MEMORY"


class UsageState(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


@dataclass
class LearningOutcomeRecord:
    artifact_type: ArtifactType
    artifact_id: str
    version_or_record_id: str
    task_run_id: str
    retrieved: bool
    used: str = "UNKNOWN"  # TRUE | FALSE | UNKNOWN
    task_family: str = "default_task_family"
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    recovery_required: bool = False
    observed_effect: ObservedEffect = ObservedEffect.UNKNOWN
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["artifact_type"] = self.artifact_type.value
        d["observed_effect"] = self.observed_effect.value
        d["verification_status"] = self.verification_status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningOutcomeRecord":
        d = data.copy()
        d["artifact_type"] = ArtifactType(d["artifact_type"])
        d["observed_effect"] = ObservedEffect(d["observed_effect"])
        d["verification_status"] = VerificationStatus(d["verification_status"])
        return cls(**d)


@dataclass
class SkillTelemetry:
    skill_name: str
    skill_version: str
    task_family: str = "default_task_family"
    retrieval_count: int = 0
    use_count: int = 0
    unknown_use_count: int = 0
    verified_success_count: int = 0
    verified_failure_count: int = 0
    recovery_required_count: int = 0
    rollback_count: int = 0
    last_used_at: Optional[str] = None

    @property
    def verified_success_rate(self) -> float:
        total = self.verified_success_count + self.verified_failure_count
        return (self.verified_success_count / total) if total > 0 else 0.0

    @property
    def reuse_rate(self) -> float:
        return (self.use_count / self.retrieval_count) if self.retrieval_count > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verified_success_rate"] = self.verified_success_rate
        d["reuse_rate"] = self.reuse_rate
        return d


@dataclass
class MemoryTelemetry:
    memory_id: str
    scope: MemoryScope
    scope_id: str
    key: str
    retrieval_count: int = 0
    use_count: int = 0
    unknown_use_count: int = 0
    verified_success_count: int = 0
    conflict_count: int = 0
    correction_count: int = 0
    last_used_at: Optional[str] = None
    last_confirmed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scope"] = self.scope.value
        return d


@dataclass
class CuratorEvaluationReport:
    artifact_type: ArtifactType
    artifact_id: str
    version_or_record_id: str
    decision: CuratorDecision
    observed_effect: ObservedEffect
    reason: str
    task_family: str = "default_task_family"
    metrics: Dict[str, Any] = field(default_factory=dict)
    suggested_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type.value,
            "artifact_id": self.artifact_id,
            "version_or_record_id": self.version_or_record_id,
            "decision": self.decision.value,
            "observed_effect": self.observed_effect.value,
            "reason": self.reason,
            "task_family": self.task_family,
            "metrics": self.metrics,
            "suggested_action": self.suggested_action,
        }


@dataclass
class CuratorRuntimeRollbackRequest:
    action_id: str
    task_run_id: str
    skill_name: str
    evaluated_version: str
    expected_runtime_hash: str
    rollback_target_version: str
    target_content: str
    target_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeRollbackResult:
    action_id: str
    skill_name: str
    status: str  # SUCCESS | STALE_HASH_MISMATCH | READBACK_MISMATCH | UPDATE_FAILED
    observed_before_hash: Optional[str] = None
    observed_after_hash: Optional[str] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CuratorActionRecord:
    action_id: str
    task_run_id: str
    artifact_id: str
    evaluated_version: str
    decision: CuratorDecision
    execution_status: str  # APPLIED | REJECTED_STALE | FAILED | NO_ACTION
    runtime_before_hash: Optional[str] = None
    runtime_after_hash: Optional[str] = None
    rollback_target: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: str = ""
    audit_trail: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CuratorActionRecord":
        d = data.copy()
        d["decision"] = CuratorDecision(d["decision"])
        return cls(**d)


@dataclass
class CuratorExecutionResult:
    decision: CuratorDecision
    applied: bool
    message: str
    active_version_after: Optional[str] = None
    active_memory_status_after: Optional[str] = None
    action_record: Optional[CuratorActionRecord] = None


@dataclass
class LearningHealthReport:
    active_skills_count: int
    actual_rollbacks_count: int
    retirements_recommended_count: int
    retirements_executed_count: int
    positive_skill_outcomes_count: int
    negative_skill_outcomes_count: int
    learned_skills_reused_count: int
    learned_skills_unreused_count: int
    active_memories_count: int
    superseded_memories_count: int
    memory_conflicts_count: int
    memories_reused_count: int
    corrections_count: int
    evaluations: List[CuratorEvaluationReport] = field(default_factory=list)
    actions: List[CuratorActionRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skills": {
                "active_count": self.active_skills_count,
                "actual_rollbacks": self.actual_rollbacks_count,
                "retirements_recommended": self.retirements_recommended_count,
                "retirements_executed": self.retirements_executed_count,
                "positive_outcomes": self.positive_skill_outcomes_count,
                "negative_outcomes": self.negative_skill_outcomes_count,
                "reused_count": self.learned_skills_reused_count,
                "unreused_count": self.learned_skills_unreused_count,
            },
            "memory": {
                "active_records": self.active_memories_count,
                "superseded_records": self.superseded_memories_count,
                "conflicts_observed": self.memory_conflicts_count,
                "memories_reused": self.memories_reused_count,
                "corrections_ingested": self.corrections_count,
            },
            "evaluations": [e.to_dict() for e in self.evaluations],
            "actions": [a.to_dict() for a in self.actions],
        }
EOF
