"""Curator Executor: Deterministic Execution of Lifecycle Actions with Authoritative Runtime Rollback."""

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Protocol, Any
from platform.learning.version_store import SkillVersionStore
from platform.learning.contracts import generate_sha256
from platform.memory.store import MemoryStore
from platform.memory.contracts import MemoryStatus
from platform.curator.contracts import (
    ArtifactType,
    CuratorDecision,
    CuratorEvaluationReport,
    CuratorActionRecord,
    CuratorExecutionResult,
)


class SparkSkillRuntimeAdapter(Protocol):
    """Protocol for authoritative Spark runtime skill lookup and update operations."""

    def lookup_skill(self, skill_name: str) -> Optional[dict]:
        """Returns dict with {'name': str, 'content': str, 'content_hash': str}."""
        ...

    def update_skill(self, skill_name: str, content: str) -> bool:
        """Updates runtime skill content."""
        ...


class CuratorExecutor:
    """Applies verified deterministic lifecycle actions based on evaluator reports."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        memory_store: MemoryStore,
        audit_ledger_path: Optional[str] = None,
    ):
        self.version_store = version_store
        self.memory_store = memory_store
        default_audit = os.path.expanduser("~/.spark/curator/actions.jsonl")
        self.audit_ledger_path = audit_ledger_path or default_audit
        os.makedirs(os.path.dirname(self.audit_ledger_path), exist_ok=True)

    def _record_action(self, action: CuratorActionRecord):
        with open(self.audit_ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(action.to_dict()) + "\n")

    def get_action_records(self) -> list[CuratorActionRecord]:
        if not os.path.exists(self.audit_ledger_path):
            return []
        records = []
        with open(self.audit_ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(CuratorActionRecord.from_dict(json.loads(line)))
        return records

    def apply_decision(
        self,
        report: CuratorEvaluationReport,
        runtime_adapter: Optional[Any] = None,
        task_run_id: str = "curator_lifecycle_task",
    ) -> CuratorExecutionResult:
        """Applies a lifecycle decision deterministically with pre-write and read-back validation."""
        action_id = f"act_{uuid.uuid4().hex[:8]}"

        # 1. Action: RETIRE_SKILL_VERSION (Authoritative rollback on regression)
        if report.decision == CuratorDecision.RETIRE_SKILL_VERSION:
            active_ver = self.version_store.get_active_version(report.artifact_id)
            if not active_ver:
                action = CuratorActionRecord(
                    action_id=action_id,
                    task_run_id=task_run_id,
                    artifact_id=report.artifact_id,
                    evaluated_version=report.version_or_record_id,
                    decision=report.decision,
                    execution_status="FAILED",
                    details=f"Cannot retire: active version for '{report.artifact_id}' not found.",
                )
                self._record_action(action)
                return CuratorExecutionResult(
                    decision=report.decision,
                    applied=False,
                    message=action.details,
                    action_record=action,
                )

            parent_id = active_ver.parent_version_id
            if not parent_id:
                action = CuratorActionRecord(
                    action_id=action_id,
                    task_run_id=task_run_id,
                    artifact_id=report.artifact_id,
                    evaluated_version=report.version_or_record_id,
                    decision=report.decision,
                    execution_status="FAILED",
                    details=f"Cannot retire: baseline version {active_ver.version_id} has no parent to roll back to.",
                )
                self._record_action(action)
                return CuratorExecutionResult(
                    decision=report.decision,
                    applied=False,
                    message=action.details,
                    action_record=action,
                )

            parent_ver = self.version_store.get_version(report.artifact_id, parent_id)
            if not parent_ver:
                action = CuratorActionRecord(
                    action_id=action_id,
                    task_run_id=task_run_id,
                    artifact_id=report.artifact_id,
                    evaluated_version=report.version_or_record_id,
                    decision=report.decision,
                    execution_status="FAILED",
                    details=f"Cannot retire: parent version record '{parent_id}' is missing.",
                )
                self._record_action(action)
                return CuratorExecutionResult(
                    decision=report.decision,
                    applied=False,
                    message=action.details,
                    action_record=action,
                )

            before_hash = active_ver.content_hash
            after_hash = parent_ver.content_hash

            # Step 1-4: Authoritative runtime transaction if adapter provided
            if runtime_adapter is not None:
                # Pre-write lookup
                current_runtime = runtime_adapter.lookup_skill(report.artifact_id)
                if not current_runtime:
                    action = CuratorActionRecord(
                        action_id=action_id,
                        task_run_id=task_run_id,
                        artifact_id=report.artifact_id,
                        evaluated_version=report.version_or_record_id,
                        decision=report.decision,
                        execution_status="FAILED",
                        details="Runtime lookup failed: skill not found in active runtime.",
                    )
                    self._record_action(action)
                    return CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

                # Stale check: verify current runtime hash matches evaluated version
                runtime_current_hash = current_runtime.get("content_hash") or generate_sha256(current_runtime.get("content", ""))
                if runtime_current_hash != active_ver.content_hash:
                    action = CuratorActionRecord(
                        action_id=action_id,
                        task_run_id=task_run_id,
                        artifact_id=report.artifact_id,
                        evaluated_version=report.version_or_record_id,
                        decision=report.decision,
                        execution_status="REJECTED_STALE",
                        runtime_before_hash=runtime_current_hash,
                        details=f"Stale curator action: active runtime hash ({runtime_current_hash[:8]}) differs from evaluated version ({active_ver.content_hash[:8]}).",
                    )
                    self._record_action(action)
                    return CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

                # Authoritative runtime update
                update_ok = runtime_adapter.update_skill(report.artifact_id, parent_ver.content)
                if not update_ok:
                    action = CuratorActionRecord(
                        action_id=action_id,
                        task_run_id=task_run_id,
                        artifact_id=report.artifact_id,
                        evaluated_version=report.version_or_record_id,
                        decision=report.decision,
                        execution_status="FAILED",
                        details="Runtime update failed during authoritative rollback.",
                    )
                    self._record_action(action)
                    return CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

                # Read-back verification
                readback = runtime_adapter.lookup_skill(report.artifact_id)
                readback_hash = readback.get("content_hash") or generate_sha256(readback.get("content", ""))
                if readback_hash != parent_ver.content_hash:
                    action = CuratorActionRecord(
                        action_id=action_id,
                        task_run_id=task_run_id,
                        artifact_id=report.artifact_id,
                        evaluated_version=report.version_or_record_id,
                        decision=report.decision,
                        execution_status="FAILED",
                        runtime_after_hash=readback_hash,
                        details=f"Read-back verification mismatch: expected parent hash {parent_ver.content_hash[:8]}, got {readback_hash[:8]}.",
                    )
                    self._record_action(action)
                    return CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

            # Step 5: Finalize local version store after verified runtime update
            ok, msg, restored = self.version_store.rollback(
                skill_name=report.artifact_id,
                target_version_id=parent_id,
                reason=report.reason,
            )
            if not ok or not restored:
                action = CuratorActionRecord(
                    action_id=action_id,
                    task_run_id=task_run_id,
                    artifact_id=report.artifact_id,
                    evaluated_version=report.version_or_record_id,
                    decision=report.decision,
                    execution_status="FAILED",
                    details=f"Version store rollback failed: {msg}",
                )
                self._record_action(action)
                return CuratorExecutionResult(decision=report.decision, applied=False, message=msg, action_record=action)

            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=task_run_id,
                artifact_id=report.artifact_id,
                evaluated_version=report.version_or_record_id,
                decision=report.decision,
                execution_status="APPLIED",
                runtime_before_hash=before_hash,
                runtime_after_hash=after_hash,
                rollback_target=parent_id,
                details=f"Successfully retired {active_ver.version_id} and restored parent {parent_id}.",
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=report.decision,
                applied=True,
                message=action.details,
                active_version_after=parent_id,
                action_record=action,
            )

        # 2. Action: ARCHIVE_MEMORY
        elif report.decision == CuratorDecision.ARCHIVE_MEMORY:
            mem = self.memory_store.get_memory(report.version_or_record_id)
            if not mem:
                return CuratorExecutionResult(decision=report.decision, applied=False, message="Memory record not found.")
            mem.status = MemoryStatus.ARCHIVED
            self.memory_store.backend.put(mem)
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=task_run_id,
                artifact_id=report.artifact_id,
                evaluated_version=report.version_or_record_id,
                decision=report.decision,
                execution_status="APPLIED",
                details=f"Memory record '{mem.id}' status set to ARCHIVED.",
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=report.decision,
                applied=True,
                message=action.details,
                active_memory_status_after=MemoryStatus.ARCHIVED.value,
                action_record=action,
            )

        # 3. Action: MARK_STALE
        elif report.decision == CuratorDecision.MARK_STALE:
            mem = self.memory_store.get_memory(report.version_or_record_id)
            if not mem:
                return CuratorExecutionResult(decision=report.decision, applied=False, message="Memory record not found.")
            mem.status = MemoryStatus.STALE
            self.memory_store.backend.put(mem)
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=task_run_id,
                artifact_id=report.artifact_id,
                evaluated_version=report.version_or_record_id,
                decision=report.decision,
                execution_status="APPLIED",
                details=f"Memory record '{mem.id}' marked STALE for revalidation.",
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=report.decision,
                applied=True,
                message=action.details,
                active_memory_status_after=MemoryStatus.STALE.value,
                action_record=action,
            )

        return CuratorExecutionResult(
            decision=report.decision,
            applied=False,
            message="No mutation required.",
            active_version_after=report.version_or_record_id,
        )
EOF
