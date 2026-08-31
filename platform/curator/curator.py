from __future__ import annotations
from typing import List, Optional
from platform.curator.contracts import CuratorRecommendation
from platform.curator.evaluator import CuratorEvaluator
from platform.curator.executor import CuratorExecutor
from platform.curator.telemetry import CuratorTelemetry

class SkillCurator:
    """Orchestrates evaluation and maintenance execution across skills and memory."""

    def __init__(
        self,
        evaluator: CuratorEvaluator,
        executor: CuratorExecutor,
        telemetry: Optional[CuratorTelemetry] = None,
    ):
        self.evaluator = evaluator
        self.executor = executor
        self.telemetry = telemetry

    def run_maintenance_cycle(self, skill_name: str) -> List[CuratorRecommendation]:
        recs = self.evaluator.evaluate_skill_performance(skill_name)
        for r in recs:
            if r.priority == "HIGH":
                # Automatically execute high-priority fixes (e.g. rollback)
                self.executor.execute_action(r.to_action())
        return recs
