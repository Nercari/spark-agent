"""Curator Executor: Deterministic Execution of Lifecycle Actions with Authoritative Runtime Rollback."""

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Protocol, Any, List, Tuple
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
    CuratorRuntimeRollbackRequest,
    RuntimeRollbackResult,
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

    def get_action_records(self) -> List[CuratorActionRecord]:
        if not os.path.exists(self.audit_ledger_path):
            return []
        records = []
        with open(self.audit_ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(CuratorActionRecord.from_dict(json.loads(line)))
        return records

    def prepare_runtime_rollback_request(
        self,
        report: CuratorEvaluationReport,
        task_run_id: str = "curator_lifecycle_task",
    ) -> Tuple[Optional[CuratorRuntimeRollbackRequest], CuratorExecutionResult]:
        """Prepares an authoritative runtime rollback request contract without mutating local state."""
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        audit_trail = ["REQUEST_PREPARED"]

        if report.decision != CuratorDecision.RETIRE_SKILL_VERSION:
            return None, CuratorExecutionResult(
                decision=report.decision,
                applied=False,
                message="Cannot prepare rollback: decision is not RETIRE_SKILL_VERSION.",
            )

        active_ver = self.version_store.get_active_version(report.artifact_id)
        if not active_ver:
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=task_run_id,
                artifact_id=report.artifact_id,
                evaluated_version=report.version_or_record_id,
                decision=report.decision,
                execution_status="FAILED",
                details=f"Cannot prepare rollback: active version for '{report.artifact_id}' not found.",
                audit_trail=audit_trail,
            )
            self._record_action(action)
            return None, CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

        parent_id = active_ver.parent_version_id
        if not parent_id:
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=task_run_id,
                artifact_id=report.artifact_id,
                evaluated_version=report.version_or_record_id,
                decision=report.decision,
                execution_status="FAILED",
                details=f"Cannot prepare rollback: baseline version {active_ver.version_id} has no parent.",
                audit_trail=audit_trail,
            )
            self._record_action(action)
            return None, CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

        parent_ver = self.version_store.get_version(report.artifact_id, parent_id)
        if not parent_ver:
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=task_run_id,
                artifact_id=report.artifact_id,
                evaluated_version=report.version_or_record_id,
                decision=report.decision,
                execution_status="FAILED",
                details=f"Cannot prepare rollback: parent version '{parent_id}' missing.",
                audit_trail=audit_trail,
            )
            self._record_action(action)
            return None, CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

        req = CuratorRuntimeRollbackRequest(
            action_id=action_id,
            task_run_id=task_run_id,
            skill_name=report.artifact_id,
            evaluated_version=report.version_or_record_id,
            expected_runtime_hash=active_ver.content_hash,
            rollback_target_version=parent_id,
            target_content=parent_ver.content,
            target_hash=parent_ver.content_hash,
        )

        action = CuratorActionRecord(
            action_id=action_id,
            task_run_id=task_run_id,
            artifact_id=report.artifact_id,
            evaluated_version=report.version_or_record_id,
            decision=report.decision,
            execution_status="PENDING_RUNTIME_ACTION",
            runtime_before_hash=active_ver.content_hash,
            runtime_after_hash=parent_ver.content_hash,
            rollback_target=parent_id,
            details="Rollback request prepared; pending host runtime execution.",
            audit_trail=audit_trail,
        )
        self._record_action(action)

        return req, CuratorExecutionResult(
            decision=report.decision,
            applied=False,
            message="Runtime rollback request prepared; pending host execution.",
            action_record=action,
        )

    def apply_decision(
        self,
        report: CuratorEvaluationReport,
        runtime_adapter: Optional[Any] = None,
        allow_local_fallback: bool = False,
        task_run_id: str = "curator_lifecycle_task",
    ) -> CuratorExecutionResult:
        """Applies a lifecycle decision deterministically with pre-write and read-back validation."""
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        audit_trail: List[str] = []

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
                    details=f"Cannot retire: active version for '{report.artifact_id}' not found in version store.",
                    audit_trail=audit_trail,
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
                    audit_trail=audit_trail,
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
                    audit_trail=audit_trail,
                )
                self._record_action(action)
                return CuratorExecutionResult(
                    decision=report.decision,
                    applied=False,
                    message=action.details,
                    action_record=action,
                )

            if runtime_adapter is None and not allow_local_fallback:
                # Prepare pending runtime action request rather than performing local mutation
                _, prep_res = self.prepare_runtime_rollback_request(report, task_run_id)
                return prep_res

            before_hash = active_ver.content_hash
            after_hash = parent_ver.content_hash

            if runtime_adapter is not None:
                current_runtime = runtime_adapter.lookup_skill(report.artifact_id)
                audit_trail.append("RUNTIME_SKILL_LOOKUP")
                if not current_runtime:
                    action = CuratorActionRecord(
                        action_id=action_id,
                        task_run_id=task_run_id,
                        artifact_id=report.artifact_id,
                        evaluated_version=report.version_or_record_id,
                        decision=report.decision,
                        execution_status="FAILED",
                        details="Runtime lookup failed: skill not found in active runtime.",
                        audit_trail=audit_trail,
                    )
                    self._record_action(action)
                    return CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

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
                        audit_trail=audit_trail,
                    )
                    self._record_action(action)
                    return CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

                update_ok = runtime_adapter.update_skill(report.artifact_id, parent_ver.content)
                audit_trail.append("RUNTIME_SKILL_UPDATE")
                if not update_ok:
                    action = CuratorActionRecord(
                        action_id=action_id,
                        task_run_id=task_run_id,
                        artifact_id=report.artifact_id,
                        evaluated_version=report.version_or_record_id,
                        decision=report.decision,
                        execution_status="FAILED",
                        details="Runtime update failed during authoritative rollback.",
                        audit_trail=audit_trail,
                    )
                    self._record_action(action)
                    return CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

                readback = runtime_adapter.lookup_skill(report.artifact_id)
                audit_trail.append("RUNTIME_SKILL_READBACK")
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
                        audit_trail=audit_trail,
                    )
                    self._record_action(action)
                    return CuratorExecutionResult(decision=report.decision, applied=False, message=action.details, action_record=action)

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
                    audit_trail=audit_trail,
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
                audit_trail=audit_trail,
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=report.decision,
                applied=True,
                message=action.details,
                active_version_after=parent_id,
                action_record=action,
            )

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
                audit_trail=["MEMORY_STATUS_UPDATE"],
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=report.decision,
                applied=True,
                message=action.details,
                active_memory_status_after=MemoryStatus.ARCHIVED.value,
                action_record=action,
            )

        elif report.decision == CuratorDecision.MARK_STALE:
            mem = self.memory_store.get_memory(report.version_or_record_id)
            if not mem:
                return CuratorExecutionResult(decision=report.decision, applied=False, message="Memory record not found.")
            # Set revalidation_needed flag without destroying active status
            mem.metadata["revalidation_needed"] = True
            self.memory_store.backend.put(mem)
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=task_run_id,
                artifact_id=report.artifact_id,
                evaluated_version=report.version_or_record_id,
                decision=report.decision,
                execution_status="APPLIED",
                details=f"Memory record '{mem.id}' flagged for revalidation while maintaining standing active truth.",
                audit_trail=["MEMORY_REVALIDATION_FLAGGED"],
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=report.decision,
                applied=True,
                message=action.details,
                active_memory_status_after=mem.status.value,
                action_record=action,
            )

        return CuratorExecutionResult(
            decision=report.decision,
            applied=False,
            message="No mutation required.",
            active_version_after=report.version_or_record_id,
        )

    def consume_runtime_result(
        self,
        request: CuratorRuntimeRollbackRequest,
        result: RuntimeRollbackResult,
    ) -> CuratorExecutionResult:
        """Processes an authoritative runtime rollback result returned from external Spark tool orchestration."""
        action_id = request.action_id
        audit_trail = ["RUNTIME_SKILL_LOOKUP", "RUNTIME_SKILL_UPDATE", "RUNTIME_SKILL_READBACK"]

        # Step 1: Validate action_id binding
        if result.action_id != request.action_id:
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=request.task_run_id,
                artifact_id=request.skill_name,
                evaluated_version=request.evaluated_version,
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                execution_status="FAILED",
                details=f"Mismatched action_id in runtime result: expected {request.action_id}, got {result.action_id}",
                audit_trail=audit_trail,
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                applied=False,
                message=action.details,
                action_record=action,
            )

        if result.status != "SUCCESS":
            status = "REJECTED_STALE" if result.status == "STALE_HASH_MISMATCH" else "FAILED"
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=request.task_run_id,
                artifact_id=request.skill_name,
                evaluated_version=request.evaluated_version,
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                execution_status=status,
                runtime_before_hash=result.observed_before_hash,
                runtime_after_hash=result.observed_after_hash,
                details=f"Runtime rollback rejected or failed: {result.message}",
                audit_trail=audit_trail,
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                applied=False,
                message=action.details,
                action_record=action,
            )

        # Step 2: Validate hashes
        if result.observed_before_hash != request.expected_runtime_hash:
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=request.task_run_id,
                artifact_id=request.skill_name,
                evaluated_version=request.evaluated_version,
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                execution_status="REJECTED_STALE",
                runtime_before_hash=result.observed_before_hash,
                details=f"Stale curator action: observed before hash ({result.observed_before_hash}) != expected ({request.expected_runtime_hash})",
                audit_trail=audit_trail,
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                applied=False,
                message=action.details,
                action_record=action,
            )

        if result.observed_after_hash != request.target_hash:
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=request.task_run_id,
                artifact_id=request.skill_name,
                evaluated_version=request.evaluated_version,
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                execution_status="FAILED",
                runtime_after_hash=result.observed_after_hash,
                details=f"Read-back verification mismatch: observed after hash ({result.observed_after_hash}) != target ({request.target_hash})",
                audit_trail=audit_trail,
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                applied=False,
                message=action.details,
                action_record=action,
            )

        # Step 3: Finalize local version store
        ok, msg, restored = self.version_store.rollback(
            skill_name=request.skill_name,
            target_version_id=request.rollback_target_version,
            reason=f"Authoritative runtime rollback verified for {request.evaluated_version}",
        )
        if not ok or not restored:
            action = CuratorActionRecord(
                action_id=action_id,
                task_run_id=request.task_run_id,
                artifact_id=request.skill_name,
                evaluated_version=request.evaluated_version,
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                execution_status="FAILED",
                details=f"Local version store rollback failed after verified runtime update: {msg}",
                audit_trail=audit_trail,
            )
            self._record_action(action)
            return CuratorExecutionResult(
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                applied=False,
                message=msg,
                action_record=action,
            )

        action = CuratorActionRecord(
            action_id=action_id,
            task_run_id=request.task_run_id,
            artifact_id=request.skill_name,
            evaluated_version=request.evaluated_version,
            decision=CuratorDecision.RETIRE_SKILL_VERSION,
            execution_status="APPLIED",
            runtime_before_hash=result.observed_before_hash,
            runtime_after_hash=result.observed_after_hash,
            rollback_target=request.rollback_target_version,
            details=f"Successfully retired {request.evaluated_version} and restored {request.rollback_target_version}.",
            audit_trail=audit_trail,
        )
        self._record_action(action)
        return CuratorExecutionResult(
            decision=CuratorDecision.RETIRE_SKILL_VERSION,
            applied=True,
            message=action.details,
            active_version_after=request.rollback_target_version,
            action_record=action,
        )
