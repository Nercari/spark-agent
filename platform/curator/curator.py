"""Autonomous Learning Curator: Unified Evaluator, Executor, and Lifecycle Coordinator."""

from typing import Dict, List, Optional, Tuple, Any
from platform.learning.version_store import SkillVersionStore
from platform.memory.store import MemoryStore
from platform.memory.contracts import MemoryStatus
from platform.curator.contracts import (
    ArtifactType,
    ObservedEffect,
    CuratorDecision,
    CuratorEvaluationReport,
    CuratorExecutionResult,
    CuratorActionRecord,
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
        audit_ledger_path: Optional[str] = None,
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
            audit_ledger_path=audit_ledger_path,
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
        runtime_adapter: Optional[Any] = None,
        allow_local_fallback: bool = False,
        task_run_id: str = "curator_lifecycle_task",
    ) -> Tuple[CuratorEvaluationReport, CuratorExecutionResult]:
        """Automatically evaluates and applies required lifecycle mutations when triggered."""
        report = self.evaluator.evaluate_skill_version(
            skill_name=skill_name,
            version_id=version_id,
            task_family=task_family,
        )

        if report.decision == CuratorDecision.RETIRE_SKILL_VERSION:
            result = self.executor.apply_decision(
                report=report,
                runtime_adapter=runtime_adapter,
                allow_local_fallback=allow_local_fallback,
                task_run_id=task_run_id,
            )
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
        action_records = self.executor.get_action_records()

        skill_recs = [r for r in records if r.artifact_type == ArtifactType.SKILL]
        mem_recs = [r for r in records if r.artifact_type == ArtifactType.MEMORY]

        positive_skills = sum(1 for r in skill_recs if r.observed_effect == ObservedEffect.POSITIVE)
        negative_skills = sum(1 for r in skill_recs if r.observed_effect == ObservedEffect.NEGATIVE)
        reused_skills = len(set(r.version_or_record_id for r in skill_recs if r.used == "TRUE"))
        unreused_skills = len(set(r.version_or_record_id for r in skill_recs if r.used == "FALSE"))

        actual_rollbacks = sum(1 for a in action_records if a.execution_status == "APPLIED" and a.decision == CuratorDecision.RETIRE_SKILL_VERSION)
        retirements_rec = sum(1 for a in action_records if a.decision == CuratorDecision.RETIRE_SKILL_VERSION)

        active_mems = self.memory_store.retrieve_memories(status=MemoryStatus.ACTIVE)
        superseded_mems = self.memory_store.retrieve_memories(status=MemoryStatus.SUPERSEDED)
        conflicted_count = sum(len(m.metadata.get("candidate_conflicts", [])) for m in active_mems)
        reused_mems = len(set(r.artifact_id for r in mem_recs if r.used == "TRUE"))
        corrections = len([m for m in active_mems if m.kind.value == "CORRECTION"])

        return LearningHealthReport(
            active_skills_count=len(self.version_store.list_skills()),
            actual_rollbacks_count=actual_rollbacks,
            retirements_recommended_count=retirements_rec,
            retirements_executed_count=actual_rollbacks,
            positive_skill_outcomes_count=positive_skills,
            negative_skill_outcomes_count=negative_skills,
            learned_skills_reused_count=reused_skills,
            learned_skills_unreused_count=unreused_skills,
            active_memories_count=len(active_mems),
            superseded_memories_count=len(superseded_mems),
            memory_conflicts_count=conflicted_count,
            memories_reused_count=reused_mems,
            corrections_count=corrections,
            actions=action_records,
        )
