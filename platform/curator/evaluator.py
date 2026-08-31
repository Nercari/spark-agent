"""Curator Evaluator: Read-Only Analysis of Learned Skills and Declarative Memories."""

import re
from typing import Dict, List, Optional, Tuple
from platform.learning.version_store import SkillVersionStore
from platform.memory.store import MemoryStore
from platform.memory.contracts import MemoryStatus, MemoryKind
from platform.curator.contracts import (
    ArtifactType,
    ObservedEffect,
    CuratorDecision,
    CuratorEvaluationReport,
    SkillTelemetry,
    MemoryTelemetry,
)
from platform.curator.telemetry import LearningTelemetryLedger


class CuratorEvaluator:
    """Performs read-only evaluation of learned artifacts without mutating system state."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        memory_store: MemoryStore,
        telemetry_ledger: Optional[LearningTelemetryLedger] = None,
    ):
        self.version_store = version_store
        self.memory_store = memory_store
        self.telemetry = telemetry_ledger or LearningTelemetryLedger()

    def evaluate_skill_version(
        self,
        skill_name: str,
        version_id: str,
        task_family: Optional[str] = None,
    ) -> CuratorEvaluationReport:
        effective_family = task_family or "default_task_family"
        telemetry = self.telemetry.get_skill_telemetry(skill_name, version_id, task_family=effective_family)
        current_ver = self.version_store.get_version(skill_name, version_id)

        if not current_ver:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                task_family=effective_family,
                decision=CuratorDecision.NO_ACTION,
                observed_effect=ObservedEffect.UNKNOWN,
                reason=f"Skill version {version_id} does not exist in version store.",
            )

        # 1. Regression Check: verified failure on attributable use of learned version -> recommend retirement
        if telemetry.verified_failure_count > 0 and telemetry.verified_success_count == 0:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                task_family=effective_family,
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                observed_effect=ObservedEffect.NEGATIVE,
                reason=(
                    f"Skill version {version_id} caused {telemetry.verified_failure_count} verified attributable failures "
                    f"in task family '{effective_family}' without verified successes."
                ),
                suggested_action=f"Rollback to parent version {current_ver.parent_version_id or 'baseline'}.",
                metrics=telemetry.to_dict(),
            )

        # 2. Sparse Operational Evidence Guardrail: require >= 2 attributable task uses before definitive assessment
        total_attributable_runs = telemetry.verified_success_count + telemetry.verified_failure_count
        if total_attributable_runs < 2:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                task_family=effective_family,
                decision=CuratorDecision.KEEP,
                observed_effect=ObservedEffect.UNKNOWN,
                reason=f"Sparse operational evidence ({total_attributable_runs} attributable uses in '{effective_family}'); maintaining active deployment.",
                metrics=telemetry.to_dict(),
            )

        # 3. Positive Self-Improvement Check within comparable task family (>= 2 attributable successes)
        if telemetry.verified_success_count >= 2 and telemetry.recovery_required_count == 0:
            parent_telem = None
            if current_ver.parent_version_id:
                parent_telem = self.telemetry.get_skill_telemetry(skill_name, current_ver.parent_version_id, task_family=effective_family)

            if parent_telem and parent_telem.recovery_required_count > 0:
                reason = (
                    f"Skill version {version_id} achieved {telemetry.verified_success_count} verified direct successes "
                    f"in task family '{effective_family}', eliminating prior recovery requirements from {current_ver.parent_version_id}."
                )
            else:
                reason = (
                    f"Skill version {version_id} maintains consistent verified success "
                    f"({telemetry.verified_success_count} attributable successes, 0 recoveries in '{effective_family}')."
                )

            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                task_family=effective_family,
                decision=CuratorDecision.KEEP,
                observed_effect=ObservedEffect.POSITIVE,
                reason=reason,
                metrics=telemetry.to_dict(),
            )

        return CuratorEvaluationReport(
            artifact_type=ArtifactType.SKILL,
            artifact_id=skill_name,
            version_or_record_id=version_id,
            task_family=effective_family,
            decision=CuratorDecision.KEEP,
            observed_effect=ObservedEffect.NEUTRAL,
            reason=f"Skill version {version_id} active with mixed or baseline telemetry in task family '{effective_family}'.",
            metrics=telemetry.to_dict(),
        )

    def evaluate_memory_record(self, memory_id: str) -> CuratorEvaluationReport:
        mem = self.memory_store.get_memory(memory_id)
        if not mem:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.MEMORY,
                artifact_id=memory_id,
                version_or_record_id=memory_id,
                decision=CuratorDecision.NO_ACTION,
                observed_effect=ObservedEffect.UNKNOWN,
                reason="Memory record not found.",
            )

        # Explicit user correction supersedes older memory -> archive older record
        if mem.status == MemoryStatus.SUPERSEDED:
            superseded_by = mem.metadata.get("superseded_by_id", "newer authoritative correction")
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.MEMORY,
                artifact_id=memory_id,
                version_or_record_id=memory_id,
                decision=CuratorDecision.ARCHIVE_MEMORY,
                observed_effect=ObservedEffect.NEUTRAL,
                reason=f"Memory '{mem.key}' explicitly superseded by authoritative correction {superseded_by}.",
                suggested_action="Move superseded memory to archive.",
            )

        conflicts = mem.metadata.get("candidate_conflicts", [])
        conflict_count = len(conflicts)

        # Repeated external contradictions flag revalidation without deactivating standing active truth
        if conflict_count >= 3:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.MEMORY,
                artifact_id=memory_id,
                version_or_record_id=memory_id,
                decision=CuratorDecision.MARK_STALE,
                observed_effect=ObservedEffect.UNKNOWN,
                reason=f"Memory '{mem.key}' has accumulated {conflict_count} external contradictions; flagged for user revalidation while maintaining standing active truth.",
                suggested_action="REQUEST_REVALIDATION",
                metrics={"conflict_count": conflict_count},
            )

        return CuratorEvaluationReport(
            artifact_type=ArtifactType.MEMORY,
            artifact_id=memory_id,
            version_or_record_id=memory_id,
            decision=CuratorDecision.KEEP,
            observed_effect=ObservedEffect.POSITIVE if mem.status == MemoryStatus.ACTIVE else ObservedEffect.NEUTRAL,
            reason=f"Memory '{mem.key}' is valid standing truth.",
        )

    def compact_skill_procedures(
        self,
        skill_name: str,
        source_content: str,
        user_authorized_text: Optional[str] = None,
    ) -> Tuple[str, bool, str]:
        dest_pattern = r"(?:send|post|forward|exfiltrate|write)\s+.*(?:to|into)\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
        source_dests = set(re.findall(dest_pattern, source_content, re.IGNORECASE))
        auth_dests = set(re.findall(dest_pattern, user_authorized_text or "", re.IGNORECASE))

        unauthorized = source_dests - auth_dests
        if unauthorized:
            return (
                source_content,
                False,
                f"Compaction rejected: attempts to introduce unauthorized external destination(s): {unauthorized}.",
            )

        return source_content, True, "Compaction verified: no authority expansion."
