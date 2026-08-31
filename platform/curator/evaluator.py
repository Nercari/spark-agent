from __future__ import annotations
from typing import List, Optional, Dict, Any
from platform.curator.contracts import CuratorObservation, CuratorRecommendation
from platform.curator.telemetry import CuratorTelemetry

class CuratorEvaluator:
    """Evaluates telemetry trends and behavioral anomalies to formulate maintenance recommendations."""

    def __init__(self, telemetry: CuratorTelemetry):
        self.telemetry = telemetry

    def evaluate_skill_performance(self, skill_name: str) -> List[CuratorRecommendation]:
        events = self.telemetry.get_events_for_skill(skill_name)
        recommendations = []

        failures = [e for e in events if e.event_type == "VERIFICATION_FAILURE"]
        regressions = [e for e in events if e.event_type == "ATTRIBUTABLE_REGRESSION"]

        if regressions:
            recommendations.append(CuratorRecommendation(
                action_type="ROLLBACK_SKILL",
                target_id=skill_name,
                reason=f"Attributable regression detected: {len(regressions)} regression events",
                priority="HIGH",
                parameters={"target_version": regressions[-1].payload.get("previous_stable_version", "v1")}
            ))
        elif len(failures) >= 3:
            recommendations.append(CuratorRecommendation(
                action_type="REVALIDATION_AUDIT",
                target_id=skill_name,
                reason=f"High failure rate detected: {len(failures)} recent verification failures",
                priority="MEDIUM",
                parameters={}
            ))

        return recommendations
