from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

@dataclass
class TelemetryEvent:
    event_id: str
    event_type: str
    skill_name: Optional[str]
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TelemetryReport:
    total_events: int
    events_by_skill: Dict[str, int]
    timestamp: float

@dataclass
class CuratorObservation:
    skill_name: str
    failure_rate: float
    regression_detected: bool
    details: str

@dataclass
class CuratorAction:
    action_type: str
    target_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CuratorRecommendation:
    action_type: str
    target_id: str
    reason: str
    priority: str = "MEDIUM"
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_action(self) -> CuratorAction:
        return CuratorAction(
            action_type=self.action_type,
            target_id=self.target_id,
            parameters=self.parameters,
        )
