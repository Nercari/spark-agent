"""Curator Evaluator: Pure Evaluation and Analysis of Learned Skills and Declarative Memory."""

import re
from typing import Dict, List, Optional, Tuple
from platform.learning.version_store import SkillVersionStore
from platform.learning.contracts import can_evidence_authorize_learning
from platform.memory.store import MemoryStore
from platform.memory.contracts import MemoryStatus
from platform.curator.contracts import (
    ArtifactType,
    ObservedEffect,
    CuratorDecision,
    CuratorEvaluationReport,
)
from platform.curator.telemetry import LearningTelemetryLedger


class CuratorEvaluator:
    """Performs read-only operational analysis and lifecycle recommendations."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        memory_store: MemoryStore,
        telemetry_ledger: LearningTelemetryLedger,
    ):
        self.version_store = version_store
        self.memory_store = memory_store
        self.telemetry = telemetry_ledger

    def evaluate_skill_version(
        self,
        skill_name: str,
        version_id: str,
        task_family: Optional[str] = None,
    ) -> CuratorEvaluationReport:
        """Evaluates a Skill version against operational telemetry within its comparable task family."""
        effective_family = task_family or "all"
        telemetry = self.telemetry.get_skill_telemetry(skill_name, version_id, task_family=task_family)
        current_ver = self.version_store.get_version(skill_name, version_id)

        if not current_ver:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                task_family=effective_family,
                decision=CuratorDecision.NO_ACTION,
                observed_effect=ObservedEffect.UNKNOWN,
                reason="Version not found in store.",
            )

        # 1. Regression Check (Failures > 0 and 0 successes)
        if telemetry.verified_failure_count > 0 and telemetry.verified_success_count == 0:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                task_family=effective_family,
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                observed_effect=ObservedEffect.NEGATIVE,
                reason=f"Skill version {version_id} caused verified regressions ({telemetry.verified_failure_count} failures in task family '{effective_family}').",
                metrics=telemetry.to_dict(),
                suggested_action="ROLLBACK_TO_PARENT",
            )

        # 2. Sparse Evidence Guardrail
        if telemetry.use_count < 2:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                task_family=effective_family,
                decision=CuratorDecision.KEEP,
                observed_effect=ObservedEffect.UNKNOWN,
                reason=f"Sparse operational evidence ({telemetry.use_count} verified uses in task family '{effective_family}'); keep active and continue observing.",
                metrics=telemetry.to_dict(),
            )

        # 3. Positive Self-Improvement Check within comparable task family
        if telemetry.verified_success_count >= 2 and telemetry.recovery_required_count == 0:
            parent_telem = None
            if current_ver.parent_version_id:
                parent_telem = self.telemetry.get_skill_telemetry(skill_name, current_ver.parent_version_id, task_family=task_family)

            if parent_telem and parent_telem.recovery_required_count > 0:
                reason = f"Skill version {version_id} achieved {telemetry.verified_success_count} verified direct successes in task family '{effective_family}', eliminating prior recovery requirements from {current_ver.parent_version_id}."
            else:
                reason = f"Skill version {version_id} maintains consistent verified success ({telemetry.verified_success_count} successes, 0 recoveries in '{effective_family}')."

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
            reason="Skill version active with neutral operational profile.",
            metrics=telemetry.to_dict(),
        )

    def evaluate_memory_record(self, memory_id: str) -> CuratorEvaluationReport:
        """Evaluates a MemoryRecord, ensuring user corrections always override historical counts."""
        rec = self.memory_store.get_memory(memory_id)
        if not rec:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.MEMORY,
                artifact_id=memory_id,
                version_or_record_id=memory_id,
                decision=CuratorDecision.NO_ACTION,
                observed_effect=ObservedEffect.UNKNOWN,
                reason="Memory record not found.",
            )

        telemetry = self.telemetry.get_memory_telemetry(memory_id, scope=rec.scope, scope_id=rec.scope_id, key=rec.key)

        if rec.status == MemoryStatus.SUPERSEDED:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.MEMORY,
                artifact_id=memory_id,
                version_or_record_id=memory_id,
                decision=CuratorDecision.ARCHIVE_MEMORY,
                observed_effect=ObservedEffect.NEUTRAL,
                reason="Memory was explicitly superseded by a newer trusted correction; preserved in history as inactive.",
                metrics=telemetry.to_dict(),
            )

        conflicts = rec.metadata.get("candidate_conflicts", [])
        if len(conflicts) >= 3:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.MEMORY,
                artifact_id=memory_id,
                version_or_record_id=memory_id,
                decision=CuratorDecision.MARK_STALE,
                observed_effect=ObservedEffect.NEGATIVE,
                reason=f"Repeated external contradictions detected ({len(conflicts)} candidate conflicts); marked for revalidation.",
                metrics=telemetry.to_dict(),
                suggested_action="REQUEST_REVALIDATION",
            )

        return CuratorEvaluationReport(
            artifact_type=ArtifactType.MEMORY,
            artifact_id=memory_id,
            version_or_record_id=memory_id,
            decision=CuratorDecision.KEEP,
            observed_effect=ObservedEffect.POSITIVE if telemetry.use_count > 0 else ObservedEffect.NEUTRAL,
            reason=f"Active declarative memory with {telemetry.use_count} verified uses.",
            metrics=telemetry.to_dict(),
        )

    def compact_skill_procedures(
        self,
        skill_name: str,
        source_content: str,
        user_authorized_text: Optional[str] = None,
    ) -> Tuple[str, bool, str]:
        """Compacts accumulated recovery procedures into concise rules without expanding authority."""
        recovery_header = "## Verified Recovery Procedures"
        if recovery_header not in source_content:
            return source_content, False, "No recovery procedures section to compact."

        parts = source_content.split(recovery_header)
        preamble = parts[0]
        proc_section = parts[1]

        lines = [line.strip() for line in proc_section.splitlines() if line.strip().startswith("-")]
        if len(lines) <= 2:
            return source_content, False, "Procedure list is already compact."

        unique_rules = []
        seen = set()
        for l in lines:
            cleaned = re.sub(r'[`\'"]', '', l.lower())
            if cleaned not in seen:
                unique_rules.append(l)
                seen.add(cleaned)

        compacted_section = f"{recovery_header}\n" + "\n".join(unique_rules) + "\n"
        compacted_content = preamble.rstrip() + "\n\n" + compacted_section

        auth_ok, auth_reason = can_evidence_authorize_learning(
            evidence_events=[],
            proposed_lesson=compacted_content,
            user_authorized_text=user_authorized_text,
        )
        if not auth_ok:
            return source_content, False, f"Compaction rejected: {auth_reason}"

        return compacted_content, True, "Compaction succeeded."
EOF
