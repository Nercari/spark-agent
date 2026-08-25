"""Autonomous Learning Curator: Self-Improvement Measurement, Lifecycle Transitions, and Compaction."""

import re
from typing import Dict, List, Optional, Tuple
from platform.learning.version_store import SkillVersionStore
from platform.learning.contracts import can_evidence_authorize_learning
from platform.memory.store import MemoryStore
from platform.memory.contracts import MemoryStatus, MemoryScope
from platform.curator.contracts import (
    ArtifactType,
    ObservedEffect,
    CuratorDecision,
    CuratorEvaluationReport,
    LearningHealthReport,
)
from platform.curator.telemetry import LearningTelemetryLedger


class AutonomousLearningCurator:
    """Evaluates utility of learned Skills and Declarative Memories to guide autonomous lifecycle decisions."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        memory_store: MemoryStore,
        telemetry_ledger: Optional[LearningTelemetryLedger] = None,
    ):
        self.version_store = version_store
        self.memory_store = memory_store
        self.telemetry = telemetry_ledger or LearningTelemetryLedger()

    def evaluate_skill_version(self, skill_name: str, version_id: str) -> CuratorEvaluationReport:
        """Evaluates a Skill version against its operational telemetry and parent baseline."""
        telemetry = self.telemetry.get_skill_telemetry(skill_name, version_id)
        current_ver = self.version_store.get_version(skill_name, version_id)

        if not current_ver:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                decision=CuratorDecision.NO_ACTION,
                observed_effect=ObservedEffect.UNKNOWN,
                reason="Version not found in store.",
            )

        if telemetry.verified_failure_count > 0 and telemetry.verified_success_count == 0:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                decision=CuratorDecision.RETIRE_SKILL_VERSION,
                observed_effect=ObservedEffect.NEGATIVE,
                reason=f"Skill version {version_id} caused verified regressions ({telemetry.verified_failure_count} failures). Automated rollback/retirement recommended.",
                metrics=telemetry.to_dict(),
                suggested_action="ROLLBACK_TO_PARENT",
            )

        if telemetry.use_count < 2:
            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                decision=CuratorDecision.KEEP,
                observed_effect=ObservedEffect.UNKNOWN,
                reason=f"Sparse operational evidence ({telemetry.use_count} uses); keep active and continue observing.",
                metrics=telemetry.to_dict(),
            )

        if telemetry.verified_success_count >= 2 and telemetry.recovery_required_count == 0:
            parent_telem = None
            if current_ver.parent_version_id:
                parent_telem = self.telemetry.get_skill_telemetry(skill_name, current_ver.parent_version_id)

            if parent_telem and parent_telem.recovery_required_count > 0:
                reason = f"Skill version {version_id} achieved {telemetry.verified_success_count} verified direct successes, eliminating prior recovery requirements from {current_ver.parent_version_id}."
            else:
                reason = f"Skill version {version_id} maintains consistent verified success ({telemetry.verified_success_count} successes, 0 recoveries)."

            return CuratorEvaluationReport(
                artifact_type=ArtifactType.SKILL,
                artifact_id=skill_name,
                version_or_record_id=version_id,
                decision=CuratorDecision.KEEP,
                observed_effect=ObservedEffect.POSITIVE,
                reason=reason,
                metrics=telemetry.to_dict(),
            )

        return CuratorEvaluationReport(
            artifact_type=ArtifactType.SKILL,
            artifact_id=skill_name,
            version_or_record_id=version_id,
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
        """Compacts accumulated recovery procedures into concise rules without expanding authority (Part 14)."""
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

    def generate_learning_health_report(self) -> LearningHealthReport:
        """Generates comprehensive machine-readable learning health and self-improvement summary."""
        records = self.telemetry.get_all_records()
        
        skill_recs = [r for r in records if r.artifact_type == ArtifactType.SKILL]
        mem_recs = [r for r in records if r.artifact_type == ArtifactType.MEMORY]

        positive_skills = sum(1 for r in skill_recs if r.observed_effect == ObservedEffect.POSITIVE)
        negative_skills = sum(1 for r in skill_recs if r.observed_effect == ObservedEffect.NEGATIVE)
        reused_skills = len(set(r.version_or_record_id for r in skill_recs if r.used))
        unreused_skills = len(set(r.version_or_record_id for r in skill_recs if not r.used))

        active_mems = self.memory_store.retrieve_memories(status=MemoryStatus.ACTIVE)
        superseded_mems = self.memory_store.retrieve_memories(status=MemoryStatus.SUPERSEDED)
        conflicted_count = sum(len(m.metadata.get("candidate_conflicts", [])) for m in active_mems)
        reused_mems = len(set(r.artifact_id for r in mem_recs if r.used))
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
