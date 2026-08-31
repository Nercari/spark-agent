"""Lifecycle Observer and Trigger Policy wiring automatic telemetry and curation into Spark tasks."""

import logging
from typing import Any, Dict, List, Optional, Tuple
from platform.learning.contracts import TaskRun, VerificationStatus
from platform.learning.version_store import SkillVersionStore
from platform.memory.contracts import MemoryRecord, MemoryScope, MemoryStatus
from platform.memory.store import MemoryStore
from platform.memory.pipeline import MemoryContextManager
from platform.curator.contracts import (
    ArtifactType,
    ObservedEffect,
    UsageState,
    SkillTelemetry,
    MemoryTelemetry,
    CuratorDecision,
    CuratorRuntimeRollbackRequest,
    RuntimeRollbackResult,
    CuratorExecutionResult,
)
from platform.curator.telemetry import LearningTelemetryLedger
from platform.curator.curator import AutonomousLearningCurator

logger = logging.getLogger(__name__)


class CuratorTriggerPolicy:
    """Determines when to trigger deterministic lifecycle curation post-task."""

    @staticmethod
    def should_evaluate_skill(
        task_run: TaskRun,
        skill_telemetry: Optional[SkillTelemetry] = None,
        effective_skill_used: Optional[UsageState] = None,
    ) -> Tuple[bool, str]:
        if task_run.verification_status == VerificationStatus.VERIFIED_FAILURE:
            # Trigger evaluation on learned version failure ONLY if skill was observably used or telemetry shows attributable failure
            if task_run.skill_version and task_run.skill_version != "v1":
                if effective_skill_used == UsageState.TRUE or (skill_telemetry and skill_telemetry.verified_failure_count > 0):
                    return True, f"verified_failure_on_learned_version_{task_run.skill_version}"

        if skill_telemetry and skill_telemetry.use_count >= 3 and (skill_telemetry.use_count % 3 == 0):
            return True, f"usage_milestone_{skill_telemetry.use_count}_reached"

        return False, "no_skill_trigger_condition_met"

    @staticmethod
    def should_evaluate_memory(
        memory_record: MemoryRecord,
        memory_telemetry: Optional[MemoryTelemetry] = None,
    ) -> Tuple[bool, str]:
        conflicts = memory_record.metadata.get("candidate_conflicts", [])
        conflict_cnt = len(conflicts)
        if memory_telemetry:
            conflict_cnt = max(conflict_cnt, memory_telemetry.conflict_count)

        if conflict_cnt >= 3:
            return True, f"repeated_memory_conflicts_count_{conflict_cnt}"

        return False, "no_memory_trigger_condition_met"


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
        allow_local_fallback: bool = False,
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
        self.allow_local_fallback = allow_local_fallback
        self.memory_context_mgr = MemoryContextManager(
            memory_store=self.memory_store,
            allow_synthetic_user_fallback=allow_synthetic_user_fallback,
        )
        self.active_tasks: Dict[str, Dict[str, Any]] = {}

    def on_task_start(
        self,
        task_run_id: str,
        skill_name: str,
        skill_version: str,
        task_family: str = "default_task_family",
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
        task_goal: Optional[str] = None,
        max_memory_budget: int = 20,
    ) -> Tuple[str, List[MemoryRecord]]:
        """Hook called at task startup: injects declarative context and records artifact retrieval state."""
        context_str, injected_memories = self.memory_context_mgr.inject_task_context(
            project_scope_id=project_scope_id,
            user_scope_id=user_scope_id,
            task_goal=task_goal,
            max_memory_budget=max_memory_budget,
        )

        mem_dict = {}
        for m in injected_memories:
            mem_dict[m.id] = {
                "id": m.id,
                "scope": m.scope,
                "scope_id": m.scope_id,
                "key": m.key,
                "retrieved": True,
                "used": UsageState.UNKNOWN,
            }

        self.active_tasks[task_run_id] = {
            "skill": {
                "name": skill_name,
                "version": skill_version,
                "task_family": task_family,
                "retrieved": True,
                "used": UsageState.UNKNOWN,
            },
            "memories": mem_dict,
            "startup_seen": True,
        }

        return context_str, injected_memories

    def on_artifact_used(
        self,
        task_run_id: str,
        artifact_type: ArtifactType,
        artifact_id: str,
        version_or_record_id: Optional[str] = None,
        used: UsageState = UsageState.TRUE,
    ):
        """Hook called when artifact use is explicitly observed during task execution."""
        if task_run_id not in self.active_tasks:
            return

        task_data = self.active_tasks[task_run_id]
        if artifact_type == ArtifactType.SKILL:
            if task_data["skill"]["name"] == artifact_id or not artifact_id:
                task_data["skill"]["used"] = used
        elif artifact_type == ArtifactType.MEMORY:
            if artifact_id in task_data["memories"]:
                task_data["memories"][artifact_id]["used"] = used

    def on_task_complete(
        self,
        task_run: TaskRun,
        recovery_required: bool = False,
        task_family: Optional[str] = None,
        skill_used: Optional[UsageState] = None,
    ) -> Dict[str, Any]:
        """Hook called at task completion: persists declarative learning, logs outcome telemetry, touches used memory, and runs curation."""
        result: Dict[str, Any] = {
            "task_run_id": task_run.id,
            "learned_memories": [],
            "curator_triggered": False,
            "curator_result": None,
            "pending_runtime_request": None,
            "memory_curator_results": [],
            "lifecycle_status": "COMPLETE",
        }

        task_state = self.active_tasks.pop(task_run.id, None)

        if task_state is not None:
            retrieved_flag = True
            startup_hook_seen = True
            effective_family = task_family or task_state["skill"]["task_family"]
            if skill_used is not None:
                effective_skill_used = skill_used
            elif task_state["skill"]["used"] != UsageState.UNKNOWN:
                effective_skill_used = task_state["skill"]["used"]
            else:
                effective_skill_used = UsageState.UNKNOWN
        else:
            retrieved_flag = False
            startup_hook_seen = False
            effective_family = task_family or "default_task_family"
            effective_skill_used = skill_used if skill_used is not None else UsageState.UNKNOWN
            result["lifecycle_status"] = "MISSING_STARTUP"

        sk_name = task_run.skill_name
        sk_ver = task_run.skill_version

        # Determine observed effect for Skill under strict attribution discipline
        effect = ObservedEffect.UNKNOWN
        if task_run.verification_status == VerificationStatus.VERIFIED_SUCCESS:
            if effective_skill_used == UsageState.TRUE and not recovery_required:
                effect = ObservedEffect.POSITIVE
            elif effective_skill_used == UsageState.TRUE and recovery_required:
                effect = ObservedEffect.NEUTRAL
            else:
                effect = ObservedEffect.UNKNOWN
        elif task_run.verification_status == VerificationStatus.VERIFIED_FAILURE:
            if effective_skill_used == UsageState.TRUE:
                effect = ObservedEffect.NEGATIVE
            else:
                effect = ObservedEffect.UNKNOWN
        else:
            effect = ObservedEffect.UNKNOWN

        # Record single final telemetry record for Skill
        try:
            self.telemetry.record_skill_outcome(
                skill_name=sk_name,
                skill_version=sk_ver,
                task_run_id=task_run.id,
                retrieved=retrieved_flag,
                used=effective_skill_used,
                task_family=effective_family,
                verification_status=task_run.verification_status,
                recovery_required=recovery_required,
                observed_effect=effect,
            )
        except Exception as e:
            logger.warning(f"Telemetry logging error for skill on task complete: {e}")

        # Record single final telemetry record for each injected Memory & touch used memories
        injected_mems = task_state["memories"] if task_state else {}
        for mem_id, mdata in injected_mems.items():
            try:
                m_used = mdata["used"]
                m_effect = ObservedEffect.UNKNOWN

                # Touch memory when used or when task verified successfully without negative indication
                if m_used == UsageState.TRUE or (m_used != UsageState.FALSE and task_run.verification_status == VerificationStatus.VERIFIED_SUCCESS):
                    self.memory_store.touch_memory_used(mem_id)

                self.telemetry.record_memory_outcome(
                    memory_id=mem_id,
                    task_run_id=task_run.id,
                    retrieved=True,
                    used=m_used,
                    verification_status=task_run.verification_status,
                    observed_effect=m_effect,
                )
            except Exception as e:
                logger.warning(f"Telemetry logging error for memory {mem_id} on task complete: {e}")

        # Ingest declarative facts and candidate conflicts
        try:
            learned_mems = self.memory_context_mgr.process_task_for_memory_learning(task_run)
            result["learned_memories"] = [m.id for m in learned_mems]
        except Exception as e:
            logger.warning(f"Memory ingestion error on task complete: {e}")

        # Evaluate Skill Curator Trigger Policy
        try:
            skill_telem = self.telemetry.get_skill_telemetry(
                skill_name=sk_name,
                skill_version=sk_ver,
                task_family=effective_family,
            )
            should_run_skill, skill_trigger_reason = CuratorTriggerPolicy.should_evaluate_skill(
                task_run=task_run,
                skill_telemetry=skill_telem,
                effective_skill_used=effective_skill_used,
            )

            if should_run_skill:
                result["curator_triggered"] = True
                result["trigger_reason"] = skill_trigger_reason
                rep = self.curator.evaluate_skill_version(
                    skill_name=sk_name,
                    version_id=sk_ver,
                    task_family=effective_family,
                )
                if rep.decision == CuratorDecision.RETIRE_SKILL_VERSION:
                    if self.runtime_adapter is not None or self.allow_local_fallback:
                        exec_res = self.curator.executor.apply_decision(
                            report=rep,
                            runtime_adapter=self.runtime_adapter,
                            allow_local_fallback=self.allow_local_fallback,
                            task_run_id=task_run.id,
                        )
                        result["curator_result"] = exec_res.to_dict()
                    else:
                        req, prep_res = self.curator.executor.prepare_runtime_rollback_request(
                            report=rep,
                            task_run_id=task_run.id,
                        )
                        result["pending_runtime_request"] = req
                        result["curator_result"] = prep_res.to_dict() if prep_res else None
        except Exception as e:
            logger.warning(f"Curator trigger evaluation error for skill: {e}")

        # Evaluate Memory Curator Trigger Policy
        try:
            candidate_mems = self.memory_store.retrieve_memories(
                scope=MemoryScope.PROJECT,
                scope_id=task_run.project_scope_id,
                status=MemoryStatus.ACTIVE,
            )
            for cm in candidate_mems:
                mem_telem = self.telemetry.get_memory_telemetry(cm.id)
                should_run_mem, mem_trigger_reason = CuratorTriggerPolicy.should_evaluate_memory(
                    memory_record=cm,
                    memory_telemetry=mem_telem,
                )
                if should_run_mem:
                    m_rep = self.curator.evaluate_memory_record(cm.id)
                    m_exec_res = self.curator.executor.apply_decision(
                        report=m_rep,
                        allow_local_fallback=True,
                        task_run_id=task_run.id,
                    )
                    result["memory_curator_results"].append(m_exec_res.to_dict())
        except Exception as e:
            logger.warning(f"Curator trigger evaluation error for memory: {e}")

        return result
