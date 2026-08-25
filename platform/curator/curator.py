"""Autonomous Learning Curator: Unified Evaluator, Executor, and Lifecycle Coordinator."""

from typing import Dict, List, Optional, Tuple
from platform.learning.version_store import SkillVersionStore
from platform.learning.backend import SparkRuntimeSkillBridge
from platform.memory.store import MemoryStore
from platform.memory.contracts import MemoryStatus
from platform.curator.contracts import (
    ArtifactType,
    ObservedEffect,
    CuratorDecision,
    CuratorEvaluationReport,
    CuratorExecutionResult,
    LearningHealthReport,
)
from platform.curator.telemetry import LearningTelemetryLedger
from platform.curator.evaluator import CuratorEvaluator
from platform.curator.executor import CuratorExecutor


class AutonomousLearningCurator:
    """Coordinates lifecycle evaluation and deterministic execution for learned Skills and Declarative Memories."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        memory_store: MemoryStore,
        telemetry_ledger: Optional[LearningTelemetryLedger] = None,
    ):
        self.version_store = version_store
        self.memory_store = memory_store
        self.telemetry = telemetry_ledger or LearningTelemetryLedger()
        self.evaluator = CuratorEvaluator(
            version_store=self.version_store,
            memory_store=self.memory_store,
            telemetry_ledger=self.telemetry,
        )
        self.executor = CuratorExecutor(
            version_store=self.version_store,
            memory_store=self.memory_store,
        )

    def evaluate_skill_version(
        self,
        skill_name: str,
        version_id: str,
        task_family: Optional[str] = None,
    ) -> CuratorEvaluationReport:
        return self.evaluator.evaluate_skill_version(
            skill_name=skill_name,
            version_id=version_id,
            task_family=task_family,
        )

    def evaluate_memory_record(self, memory_id: str) -> CuratorEvaluationReport:
        return self.evaluator.evaluate_memory_record(memory_id)

    def compact_skill_procedures(
        self,
        skill_name: str,
        source_content: str,
        user_authorized_text: Optional[str] = None,
    ) -> Tuple[str, bool, str]:
        return self.evaluator.compact_skill_procedures(
            skill_name=skill_name,
            source_content=source_content,
            user_authorized_text=user_authorized_text,
        )

    def evaluate_and_execute_if_triggered(
        self,
        skill_name: str,
        version_id: str,
        task_family: Optional[str] = None,
        trigger_reason: str = "automatic_task_completion",
        runtime_bridge: Optional[SparkRuntimeSkillBridge] = None,
    ) -> Tuple[CuratorEvaluationReport, CuratorExecutionResult]:
        """Automatically evaluates and applies required lifecycle mutations when triggered."""
        report = self.evaluator.evaluate_skill_version(
            skill_name=skill_name,
            version_id=version_id,
            task_family=task_family,
        )

        if report.decision == CuratorDecision.RETIRE_SKILL_VERSION:
            result = self.executor.apply_decision(report, runtime_bridge=runtime_bridge)
            return report, result

        result = CuratorExecutionResult(
            decision=report.decision,
            applied=False,
            message="Evaluated; no lifecycle transition triggered.",
            active_version_after=version_id,
        )
        return report, result

    def generate_learning_health_report(self) -> LearningHealthReport:
        """Generates comprehensive machine-readable learning health and self-improvement summary."""
        records = self.telemetry.get_all_records()

        skill_recs = [r for r in records if r.artifact_type == ArtifactType.SKILL]
        mem_recs = [r for r in records if r.artifact_type == ArtifactType.MEMORY]

        positive_skills = sum(1 for r in skill_recs if r.observed_effect == ObservedEffect.POSITIVE)
        negative_skills = sum(1 for r in skill_recs if r.observed_effect == ObservedEffect.NEGATIVE)
        reused_skills = len(set(r.version_or_record_id for r in skill_recs if r.used == "TRUE"))
        unreused_skills = len(set(r.version_or_record_id for r in skill_recs if r.used == "FALSE"))

        active_mems = self.memory_store.retrieve_memories(status=MemoryStatus.ACTIVE)
        superseded_mems = self.memory_store.retrieve_memories(status=MemoryStatus.SUPERSEDED)
        conflicted_count = sum(len(m.metadata.get("candidate_conflicts", [])) for m in active_mems)
        reused_mems = len(set(r.artifact_id for r in mem_recs if r.used == "TRUE"))
        corrections = len([m for m in active_mems if m.kind.value == "CORRECTION"])

        return LearningHealthReport(
            active_skills_count=len(self.version_store.list_skills()),
            versions_rolled_back_count=negative_skills,
            learned_skills_reused_count=reused_skills,
            learned_skills_unreused_count=unreused_skills,
            positive_skill_outcomes_count=positive_skills,
            negative_skill_outcomes_count=negative_skills,
            active_memories_count=len(active_mems),
            superseded_memories_count=len(superseded_mems),
            memory_conflicts_count=conflicted_count,
            memories_reused_count=reused_mems,
            corrections_count=corrections,
        )
EOF
