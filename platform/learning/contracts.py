from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

class MutationType(str, Enum):
    PATCH_INSTRUCTION = "PATCH_INSTRUCTION"
    ADD_GUARDRAIL = "ADD_GUARDRAIL"
    UPDATE_EXAMPLE = "UPDATE_EXAMPLE"
    ROLLBACK = "ROLLBACK"

@dataclass
class EvidenceEvent:
    event_id: str
    task_id: str
    event_type: str
    timestamp: float
    skill_name: Optional[str] = None
    skill_version: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TaskExecutionRecord:
    task_id: str
    goal: str
    skill_name: Optional[str] = None
    skill_version: Optional[str] = None
    verification_status: str = "UNKNOWN"
    had_recovery: bool = False
    timestamp: float = 0.0
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

@dataclass
class ProposedMutation:
    skill_name: str
    base_version: str
    mutation_type: MutationType
    proposed_content: str
    rationale: str

@dataclass
class ReflectionAnalysis:
    task_id: str
    has_salient_learning: bool
    error_category: str
    root_cause: str
    is_reusable_lesson: bool
    proposed_mutation: Optional[ProposedMutation] = None

@dataclass
class ReviewDecision:
    approved: bool
    decision_reason: str
    target_mutation: Optional[ProposedMutation] = None

@dataclass
class VerificationResult:
    passed: bool
    error_message: Optional[str] = None
