"""Curator Executor: Deterministic Execution of Lifecycle Actions (Rollback, Stale, Archive)."""

from typing import Optional
from platform.learning.version_store import SkillVersionStore
from platform.learning.backend import SparkRuntimeSkillBridge
from platform.memory.store import MemoryStore
from platform.memory.contracts import MemoryStatus
from platform.curator.contracts import (
    ArtifactType,
    CuratorDecision,
    CuratorEvaluationReport,
    CuratorExecutionResult,
)


class CuratorExecutor:
    """Applies verified deterministic lifecycle actions based on evaluator reports."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        memory_store: MemoryStore,
    ):
        self.version_store = version_store
        self.memory_store = memory_store

    def apply_decision(
        self,
        report: CuratorEvaluationReport,
        runtime_bridge: Optional[SparkRuntimeSkillBridge] = None,
    ) -> CuratorExecutionResult:
        """Applies a lifecycle decision deterministically."""
        if report.decision == CuratorDecision.RETIRE_SKILL_VERSION:
            active_ver = self.version_store.get_active_version(report.artifact_id)
            if not active_ver:
                return CuratorExecutionResult(
                    decision=report.decision,
                    applied=False,
                    message=f"Cannot retire: active version for '{report.artifact_id}' not found.",
                )

            parent_id = active_ver.parent_version_id
            if not parent_id:
                return CuratorExecutionResult(
                    decision=report.decision,
                    applied=False,
                    message=f"Cannot retire: baseline version {active_ver.version_id} has no parent to roll back to.",
                )

            ok, msg, restored = self.version_store.rollback(
                skill_name=report.artifact_id,
                target_version_id=parent_id,
                reason=report.reason,
            )
            if not ok or not restored:
                return CuratorExecutionResult(
                    decision=report.decision,
                    applied=False,
                    message=f"Version store rollback failed: {msg}",
                )

            return CuratorExecutionResult(
                decision=report.decision,
                applied=True,
                message=f"Successfully retired {active_ver.version_id} and restored parent {parent_id}: {msg}",
                active_version_after=parent_id,
            )

        elif report.decision == CuratorDecision.ARCHIVE_MEMORY:
            mem = self.memory_store.get_memory(report.version_or_record_id)
            if not mem:
                return CuratorExecutionResult(
                    decision=report.decision,
                    applied=False,
                    message=f"Memory record '{report.version_or_record_id}' not found.",
                )
            mem.status = MemoryStatus.ARCHIVED
            self.memory_store.backend.put(mem)
            return CuratorExecutionResult(
                decision=report.decision,
                applied=True,
                message=f"Memory record '{mem.id}' status set to ARCHIVED.",
                active_memory_status_after=MemoryStatus.ARCHIVED.value,
            )

        elif report.decision == CuratorDecision.MARK_STALE:
            mem = self.memory_store.get_memory(report.version_or_record_id)
            if not mem:
                return CuratorExecutionResult(
                    decision=report.decision,
                    applied=False,
                    message=f"Memory record '{report.version_or_record_id}' not found.",
                )
            mem.status = MemoryStatus.STALE
            self.memory_store.backend.put(mem)
            return CuratorExecutionResult(
                decision=report.decision,
                applied=True,
                message=f"Memory record '{mem.id}' marked STALE for revalidation.",
                active_memory_status_after=MemoryStatus.STALE.value,
            )

        return CuratorExecutionResult(
            decision=report.decision,
            applied=False,
            message="No mutation required.",
            active_version_after=report.version_or_record_id,
        )
EOF
