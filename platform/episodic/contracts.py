from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class EpisodicSearchQuery:
    skill_name: Optional[str] = None
    goal_substring: Optional[str] = None
    verification_status: Optional[str] = None
    requires_recovery: Optional[bool] = None
    project_scope: Optional[str] = None
    limit: Optional[int] = None

@dataclass
class TaskRunSummary:
    task_id: str
    goal: str
    skill_name: str
    skill_version: str
    verification_status: str
    had_recovery: bool
    timestamp: float
    project_scope: Optional[str] = None

@dataclass
class TaskRunDetail:
    task_id: str
    goal: str
    skill_name: str
    skill_version: str
    verification_status: str
    had_recovery: bool
    timestamp: float
    project_scope: Optional[str] = None
    evidence_events: List[Dict[str, Any]] = field(default_factory=list)
    recovery_attempts: List[Dict[str, Any]] = field(default_factory=list)
    error_traces: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "skill_name": self.skill_name,
            "skill_version": self.skill_version,
            "verification_status": self.verification_status,
            "had_recovery": self.had_recovery,
            "timestamp": self.timestamp,
            "project_scope": self.project_scope,
            "evidence_events": self.evidence_events,
            "recovery_attempts": self.recovery_attempts,
            "error_traces": self.error_traces,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskRunDetail:
        return cls(
            task_id=data["task_id"],
            goal=data["goal"],
            skill_name=data["skill_name"],
            skill_version=data["skill_version"],
            verification_status=data.get("verification_status", "UNKNOWN"),
            had_recovery=data.get("had_recovery", False),
            timestamp=data.get("timestamp", 0.0),
            project_scope=data.get("project_scope"),
            evidence_events=data.get("evidence_events", []),
            recovery_attempts=data.get("recovery_attempts", []),
            error_traces=data.get("error_traces", []),
        )
