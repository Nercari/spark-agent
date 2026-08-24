"""Learning Commit Engine with Read-Before-Write and Autonomous Rollback."""

import os
import json
from datetime import datetime, timezone
from typing import Optional, Tuple
from platform.learning.contracts import (
    LearningMutation,
    MutationDecision,
    SkillVersion,
)
from platform.learning.version_store import SkillVersionStore


class LearningCommitEngine:
    def __init__(self, version_store: SkillVersionStore, audit_log_path: Optional[str] = None):
        self.version_store = version_store
        self.audit_log_path = audit_log_path or "/working_dir/c_b490a8c7dd21c813/.learning/audit_ledger.jsonl"
        os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)

    def commit_mutation(self, mutation: LearningMutation) -> Tuple[bool, str, Optional[SkillVersion]]:
        """Executes atomic commit of a learning mutation with strict guardrails."""
        if mutation.target_skill.startswith("system:"):
            self._log_audit(mutation, "REJECTED_SYSTEM_SKILL", "System skills are immutable.")
            return False, "Cannot modify system skills.", None

        if mutation.decision == MutationDecision.BLOCKED_UNTRUSTED:
            self._log_audit(mutation, "BLOCKED_UNTRUSTED", mutation.reason)
            return False, f"Mutation blocked: {mutation.reason}", None

        if mutation.operation == "NO_LEARNING" or mutation.decision == MutationDecision.NO_LEARNING:
            self._log_audit(mutation, "NO_ACTION", mutation.reason)
            return True, "No learning action required.", None

        success, message, new_version = self.version_store.create_new_version(
            skill_name=mutation.target_skill,
            base_version_id=mutation.base_version_id,
            base_version_hash=mutation.base_version_hash,
            new_content=mutation.proposed_content,
            change_reason=mutation.reason,
            created_from_task_run_id=mutation.task_run_id,
        )

        if not success:
            mutation.decision = MutationDecision.REJECT_STALE
            self._log_audit(mutation, "REJECTED_STALE_WRITE", message)
            return False, message, None

        mutation.committed_at = datetime.now(timezone.utc).isoformat()
        self._log_audit(mutation, "AUTO_COMMITTED", f"Successfully activated version {new_version.version_id}")
        return True, f"Successfully auto-committed version {new_version.version_id}.", new_version

    def rollback_skill(self, skill_name: str, target_version_id: str, reason: str) -> Tuple[bool, str, Optional[SkillVersion]]:
        """Restores a previous skill version upon verified regression."""
        success, message, restored_version = self.version_store.rollback(
            skill_name=skill_name,
            target_version_id=target_version_id,
            reason=reason,
        )
        if success:
            self._log_audit_entry({
                "action": "ROLLBACK",
                "skill_name": skill_name,
                "restored_version": target_version_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return success, message, restored_version

    def _log_audit(self, mutation: LearningMutation, status: str, details: str):
        entry = {
            "mutation_id": mutation.id,
            "task_run_id": mutation.task_run_id,
            "skill_name": mutation.target_skill,
            "operation": mutation.operation,
            "status": status,
            "details": details,
            "diff": mutation.diff,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._log_audit_entry(entry)

    def _log_audit_entry(self, entry: dict):
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
