"""Contracts for progressive episodic retrieval and evidence queries."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from platform.learning.contracts import VerificationStatus


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
class EpisodicQuery:
    """Structured search parameters for querying episodic task history."""
    project_scope_id: Optional[str] = None
    skill_name: Optional[str] = None
    skill_version: Optional[str] = None
    verification_status: Optional[VerificationStatus] = None
    has_recovery: Optional[bool] = None
    tool_name_used: Optional[str] = None
    operation_id: Optional[str] = None
    limit: int = 10
    user_goal_keywords: List[str] = field(default_factory=list)


@dataclass
class RetrievedEvidenceSubset:
    """Bounded, progressive evidence subset extracted from a TaskRun without loading full payload dumps."""
    task_run_id: str
    goal: str
    verification_status: VerificationStatus
    had_recovery: bool
    relevant_operations: List[dict] = field(default_factory=list)
    recovery_evidence: Optional[dict] = None
    summary_text: str = ""
