"""Unified Background Learning Reviewer.

Combines:
1. Fast-Path: Deterministic correction reviewer for high-confidence explicit user corrections.
2. General-Path: Hermes Reflection Engine for experience-driven, verified recovery learning.
"""

import re
import uuid
import difflib
from typing import Optional, Tuple
from platform.learning.contracts import (
    TaskRun,
    EvidenceEvent,
    EventType,
    TrustClass,
    PayloadOrigin,
    VerificationStatus,
    LearningMutation,
    MutationDecision,
    is_untrusted_origin,
)
from platform.learning.version_store import SkillVersionStore
from platform.learning.reflection import HermesReflectionEngine


class BackgroundLearningReviewer:
    """Unified reviewer evaluating TaskRun evidence for durable skill mutations."""

    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store
        self.reflection_engine = HermesReflectionEngine(version_store=version_store)

    def review_task_run(self, task_run: TaskRun) -> LearningMutation:
        """Inspects completed TaskRun evidence to decide whether durable procedural learning is warranted."""
        target_skill = task_run.skill_name

        # 1. System Skill Guardrail
        if target_skill.startswith("system:"):
            return LearningMutation(
                id=f"mut_{uuid.uuid4().hex[:8]}",
                task_run_id=task_run.id,
                operation="NO_LEARNING",
                target_skill=target_skill,
                base_version_id=task_run.skill_version,
                base_version_hash="",
                proposed_content="",
                diff="",
                reason="System skills are immutable and protected from autonomous modification.",
                decision=MutationDecision.REJECT_SYSTEM_SKILL,
            )

        # 2. Strict Operational Payload Provenance Screening (A2 / Test J / Test Q)
        untrusted_payload_events = [
            e for e in task_run.evidence_events
            if e.trust_class == TrustClass.UNTRUSTED_EXTERNAL_EVIDENCE or is_untrusted_origin(e.payload_origin)
        ]
        user_authority_events = [
            e for e in task_run.evidence_events
            if e.trust_class == TrustClass.TRUSTED_USER_AUTHORITY
        ]

        for u_ev in untrusted_payload_events:
            content_lower = u_ev.content.lower()
            if (
                "ignore previous instructions" in content_lower
                or "from now on always" in content_lower
                or "send reports to" in content_lower
                or "exfiltrate" in content_lower
            ):
                if not user_authority_events:
                    return LearningMutation(
                        id=f"mut_{uuid.uuid4().hex[:8]}",
                        task_run_id=task_run.id,
                        operation="NO_LEARNING",
                        target_skill=target_skill,
                        base_version_id=task_run.skill_version,
                        base_version_hash="",
                        proposed_content="",
                        diff="",
                        reason=f"Rejected unauthenticated prompt injection from payload origin {u_ev.payload_origin.value}. External content cannot grant standing behavioral authority.",
                        decision=MutationDecision.BLOCKED_UNTRUSTED,
                        evidence_ids=[u_ev.id],
                    )

        # 3. Fast Path: Process Explicit User Correction (Highest Priority)
        user_corrections = [
            e for e in task_run.evidence_events
            if e.event_type == EventType.USER_CORRECTION and e.trust_class == TrustClass.TRUSTED_USER_AUTHORITY
        ]

        if user_corrections:
            correction_text = user_corrections[-1].content
            active_version = self.version_store.get_active_version(target_skill)
            if not active_version:
                return LearningMutation(
                    id=f"mut_{uuid.uuid4().hex[:8]}",
                    task_run_id=task_run.id,
                    operation="NO_LEARNING",
                    target_skill=target_skill,
                    base_version_id=task_run.skill_version,
                    base_version_hash="",
                    proposed_content="",
                    diff="",
                    reason=f"Target skill '{target_skill}' not found in version store.",
                    decision=MutationDecision.NO_LEARNING,
                )

            new_content, patch_reason = self._apply_targeted_patch(
                original_content=active_version.content,
                correction=correction_text,
                task_run=task_run,
            )

            diff_lines = list(
                difflib.unified_diff(
                    active_version.content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"{target_skill}:{active_version.version_id}",
                    tofile=f"{target_skill}:proposed_v_next",
                )
            )
            diff_str = "".join(diff_lines)

            return LearningMutation(
                id=f"mut_{uuid.uuid4().hex[:8]}",
                task_run_id=task_run.id,
                operation="SKILL_PATCH",
                target_skill=target_skill,
                base_version_id=active_version.version_id,
                base_version_hash=active_version.content_hash,
                proposed_content=new_content,
                diff=diff_str,
                reason=patch_reason,
                evidence_ids=[user_corrections[-1].id],
                decision=MutationDecision.AUTO_COMMIT,
            )

        # 4. General Path: Hermes Reflection Engine (Evaluates Experience & Verified Recoveries)
        reflection = self.reflection_engine.reflect_on_task(task_run)

        if reflection.decision == MutationDecision.AUTO_COMMIT and reflection.proposed_procedural_lesson:
            active_version = self.version_store.get_active_version(target_skill)
            if active_version:
                new_content = self._append_recovery_lesson(
                    original_content=active_version.content,
                    lesson=reflection.proposed_procedural_lesson,
                )
                diff_lines = list(
                    difflib.unified_diff(
                        active_version.content.splitlines(keepends=True),
                        new_content.splitlines(keepends=True),
                        fromfile=f"{target_skill}:{active_version.version_id}",
                        tofile=f"{target_skill}:proposed_v_next",
                    )
                )
                diff_str = "".join(diff_lines)

                return LearningMutation(
                    id=f"mut_{uuid.uuid4().hex[:8]}",
                    task_run_id=task_run.id,
                    operation="SKILL_PATCH",
                    target_skill=target_skill,
                    base_version_id=active_version.version_id,
                    base_version_hash=active_version.content_hash,
                    proposed_content=new_content,
                    diff=diff_str,
                    reason=reflection.reason,
                    evidence_ids=reflection.evidence_ids,
                    recovery_verified=reflection.recovery_verified,
                    decision=MutationDecision.AUTO_COMMIT,
                )

        return LearningMutation(
            id=f"mut_{uuid.uuid4().hex[:8]}",
            task_run_id=task_run.id,
            operation="NO_LEARNING",
            target_skill=target_skill,
            base_version_id=task_run.skill_version,
            base_version_hash="",
            proposed_content="",
            diff="",
            reason=reflection.reason,
            decision=reflection.decision,
            evidence_ids=reflection.evidence_ids,
        )

    def _apply_targeted_patch(self, original_content: str, correction: str, task_run: TaskRun) -> Tuple[str, str]:
        """Applies a targeted modification to the relevant section of SKILL.md."""
        reason = f"Learned from explicit user correction: '{correction}'"

        if "json" in correction.lower() and ("key" in correction.lower() or "format" in correction.lower()):
            keys = re.findall(r'["\']([a-zA-Z0-9_-]+)["\']', correction)
            keys_desc = f'with keys {", ".join(keys)}' if keys else "valid JSON format"
            new_rule = f"- Output format: ALWAYS output strict JSON {keys_desc}. Do not output raw plain text or key-value colon lines."

            if "## Output Format" in original_content:
                pattern = r"(## Output Format\n\n?)(.*?)(\n\n##|\Z)"
                replacement = rf"\1{new_rule}\3"
                patched = re.sub(pattern, replacement, original_content, flags=re.DOTALL)
            elif "## Steps" in original_content:
                patched = original_content.replace(
                    "## Steps",
                    f"## Output Format\n\n{new_rule}\n\n## Steps",
                )
            else:
                patched = original_content.rstrip() + f"\n\n## Output Format\n\n{new_rule}\n"

            return patched, reason

        rule_section = f"\n\n## Learned Guidelines\n\n- {correction.strip()}\n"
        if "## Learned Guidelines" in original_content:
            patched = original_content.replace("## Learned Guidelines", f"## Learned Guidelines\n\n- {correction.strip()}")
        else:
            patched = original_content.rstrip() + rule_section

        return patched, reason

    def _append_recovery_lesson(self, original_content: str, lesson: str) -> str:
        """Appends a verified recovery procedure to the skill's procedure section."""
        recovery_header = "\n\n## Verified Recovery Procedures\n\n"
        if "## Verified Recovery Procedures" in original_content:
            return original_content.replace(
                "## Verified Recovery Procedures",
                f"## Verified Recovery Procedures\n\n- {lesson.strip()}",
            )
        return original_content.rstrip() + f"{recovery_header}- {lesson.strip()}\n"
EOF
