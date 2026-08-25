"""Contracts for Progressive Episodic Retrieval."""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from platform.learning.contracts import VerificationStatus


@dataclass
class TaskRunSummary:
    task_run_id: str
    goal: str
    skill_name: str
    skill_version: str
    verification_status: VerificationStatus
    started_at: str
    completed_at: str
    event_count: int
    project_scope_id: str
    user_scope_id: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verification_status"] = self.verification_status.value
        return d


@dataclass
class EpisodicQuery:
    skill_name: Optional[str] = None
    project_scope_id: Optional[str] = None
    verification_status: Optional[VerificationStatus] = None
    has_error: Optional[bool] = None
    has_recovery: Optional[bool] = None
    limit: int = 10
