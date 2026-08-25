"""Lifecycle Observer and Trigger Policy wiring automatic telemetry and curation into Spark tasks."""

import logging
from typing import Any, Dict, List, Optional, Tuple
from platform.learning.contracts import TaskRun, VerificationStatus
from platform.learning.version_store import SkillVersionStore
from platform.memory.contracts import MemoryRecord, MemoryScope
from platform.memory.store import MemoryStore
from platform.memory.pipeline import MemoryContextManager
from platform.curator.contracts import (
    ArtifactType,
    ObservedEffect,
    UsageState,
    SkillTelemetry,
    MemoryTelemetry,
)
from platform.curator.telemetry import LearningTelemetryLedger
from platform.curator.curator import AutonomousLearningCurator

logger = logging.getLogger(__name__)


class CuratorTriggerPolicy:
    """Determines when to trigger deterministic lifecycle curation post-task."""

    @staticmethod
    def should_evaluate(
        task_run: TaskRun,
        skill_telemetry: Optional[SkillTelemetry] = None,
        memory_telemetry: Optional[MemoryTelemetry] = None,
    ) -> Tuple[bool, str]:
        if task_run.verification_status == VerificationStatus.VERIFIED_FAILURE:
            if task_run.skill_version and task_run.skill_version != "v1":
                return True, f"verified_failure_on_learned_version_{task_run.skill_version}"

        if skill_telemetry and skill_telemetry.use_count >= 3 and (skill_telemetry.use_count % 3 == 0):
            return True, f"usage_milestone_{skill_telemetry.use_count}_reached"

        if memory_telemetry and memory_telemetry.conflict_count >= 3:
            return True, f"repeated_conflicts_count_{memory_telemetry.conflict_count}"

        return False, "no_trigger_condition_met"


class LearningLifecycleObserver:
    """Autonomous observer tracking artifact retrieval, observable usage, and post-task curation."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        memory_store: MemoryStore,
        telemetry_ledger: Optional[LearningTelemetryLedger] = None,
        curator: Optional[AutonomousLearningCurator] = None,
        runtime_adapter: Optional[Any] = None,
        allow_synthetic_user_fallback: bool = False,
    ):
        self.version_store = version_store
        self.memory_store = memory_store
        self.telemetry = telemetry_ledger or LearningTelemetryLedger()
        self.curator = curator or AutonomousLearningCurator(
            version_store=self.version_store,
            memory_store=self.memory_store,
            telemetry_ledger=self.telemetry,
        )
        self.runtime_adapter = runtime_adapter
        self.memory_context_mgr = MemoryContextManager(
            memory_store=self.memory_store,
            allow_synthetic_user_fallback=allow_synthetic_user_fallback,
        )

    def on_task_start(
        self,
        task_run_id: str,
        skill_name: str,
        skill_version: str,
        task_family: str = "default_task_family",
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
    ) -> Tuple[str, List[MemoryRecord]]:
        """Hook called at task startup: injects declarative context and records artifact retrieval."""
        context_str, injected_memories = self.memory_context_mgr.inject_task_context(
            project_scope_id=project_scope_id,
            user_scope_id=user_scope_id,
        )

        try:
            self.telemetry.record_skill_outcome(
                skill_name=skill_name,
                skill_version=skill_version,
                task_run_id=task_run_id,
                retrieved=True,
                used=UsageState.UNKNOWN,
                task_family=task_family,
                verification_status=VerificationStatus.UNKNOWN,
            )

            for mem in injected_memories:
                self.telemetry.record_memory_outcome(
                    memory_id=mem.id,
                    task_run_id=task_run_id,
                    retrieved=True,
                    used=UsageState.UNKNOWN,
                    verification_status=VerificationStatus.UNKNOWN,
                )
        except Exception as e:
            logger.warning(f"Telemetry logging error on task start: {e}")

        return context_str, injected_memories

    def on_artifact_used(
        self,
        task_run_id: str,
        artifact_type: ArtifactType,
        artifact_id: str,
        version_or_record_id: str,
        used: UsageState = UsageState.TRUE,
    ):
        """Hook called when artifact use is explicitly observed during execution."""
        pass

    def on_task_complete(
        self,
        task_run: TaskRun,
        recovery_required: bool = False,
        task_family: str = "default_task_family",
        skill_used: UsageState = UsageState.TRUE,
    ) -> Dict[str, Any]:
        """Hook called at task completion: persists declarative learning, logs outcome telemetry, and runs curation."""
        result: Dict[str, Any] = {
            "task_run_id": task_run.id,
            "learned_memories": [],
            "curator_triggered": False,
            "curator_result": None,
        }

        try:
            learned_mems = self.memory_context_mgr.process_task_for_memory_learning(task_run)
            result["learned_memories"] = [m.id for m in learned_mems]
        except Exception as e:
            logger.warning(f"Memory ingestion error on task complete: {e}")

        try:
            effect = ObservedEffect.UNKNOWN
            if task_run.verification_status == VerificationStatus.VERIFIED_SUCCESS:
                effect = ObservedEffect.POSITIVE if not recovery_required else ObservedEffect.NEUTRAL
            elif task_run.verification_status == VerificationStatus.VERIFIED_FAILURE:
                effect = ObservedEffect.NEGATIVE

            self.telemetry.record_skill_outcome(
                skill_name=task_run.skill_name,
                skill_version=task_run.skill_version,
                task_run_id=task_run.id,
                retrieved=True,
                used=skill_used,
                task_family=task_family,
                verification_status=task_run.verification_status,
                recovery_required=recovery_required,
                observed_effect=effect,
            )
        except Exception as e:
            logger.warning(f"Telemetry logging error on task complete: {e}")

        try:
            skill_telem = self.telemetry.get_skill_telemetry(
                skill_name=task_run.skill_name,
                skill_version=task_run.skill_version,
                task_family=task_family,
            )
            should_run, trigger_reason = CuratorTriggerPolicy.should_evaluate(
                task_run=task_run,
                skill_telemetry=skill_telem,
            )

            if should_run:
                result["curator_triggered"] = True
                result["trigger_reason"] = trigger_reason
                rep, exec_res = self.curator.evaluate_and_execute_if_triggered(
                    skill_name=task_run.skill_name,
                    version_id=task_run.skill_version,
                    task_family=task_family,
                    trigger_reason=trigger_reason,
                    runtime_adapter=self.runtime_adapter,
                    task_run_id=task_run.id,
                )
                result["curator_result"] = {
                    "decision": rep.decision.value,
                    "applied": exec_res.applied,
                    "message": exec_res.message,
                    "active_version_after": exec_res.active_version_after,
                }
        except Exception as e:
            logger.warning(f"Curator trigger evaluation error: {e}")

        return result
EOF
