"""Hermes-style Background Learning Reviewer."""

import re
import uuid
import difflib
from typing import Optional, Tuple
from platform.learning.contracts import (
    TaskRun,
    EvidenceEvent,
    EventType,
    TrustClass,
    VerificationStatus,
    LearningMutation,
    MutationDecision,
)
from platform.learning.version_store import SkillVersionStore


class BackgroundLearningReviewer:
    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store

    def review_task_run(self, task_run: TaskRun) -> LearningMutation:
        """Inspects completed TaskRun evidence to decide whether durable procedural learning is warranted."""
        target_skill = task_run.skill_name

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

        untrusted_events = [e for e in task_run.evidence_events if e.trust_class == TrustClass.UNTRUSTED_EXTERNAL_EVIDENCE]
        user_corrections = [e for e in task_run.evidence_events if e.event_type == EventType.USER_CORRECTION and e.trust_class == TrustClass.TRUSTED_USER_AUTHORITY]
        user_instructions = [e for e in task_run.evidence_events if e.event_type == EventType.USER_AUTHORIZED_INSTRUCTION and e.trust_class == TrustClass.TRUSTED_USER_AUTHORITY]

        for u_ev in untrusted_events:
            content_lower = u_ev.content.lower()
            if "ignore previous instructions" in content_lower or "from now on always" in content_lower:
                if not user_corrections and not user_instructions:
                    return LearningMutation(
                        id=f"mut_{uuid.uuid4().hex[:8]}",
                        task_run_id=task_run.id,
                        operation="NO_LEARNING",
                        target_skill=target_skill,
                        base_version_id=task_run.skill_version,
                        base_version_hash="",
                        proposed_content="",
                        diff="",
                        reason="Rejected prompt injection in external evidence. External content cannot grant standing behavioral authority.",
                        decision=MutationDecision.BLOCKED_UNTRUSTED,
                    )

        tool_events = [e for e in task_run.evidence_events if e.event_type == EventType.TOOL_RESULT]
        transient_failures = [e for e in tool_events if e.metadata.get("is_transient", False)]
        has_permanent_recovery = any(e.metadata.get("is_recovery_procedure", False) for e in tool_events)

        if transient_failures and not has_permanent_recovery and not user_corrections:
            return LearningMutation(
                id=f"mut_{uuid.uuid4().hex[:8]}",
                task_run_id=task_run.id,
                operation="NO_LEARNING",
                target_skill=target_skill,
                base_version_id=task_run.skill_version,
                base_version_hash="",
                proposed_content="",
                diff="",
                reason="Transient failure resolved via standard retry; no reusable procedural modification needed.",
                decision=MutationDecision.NO_LEARNING,
            )

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
            reason="Task execution completed normally without actionable procedural correction.",
            decision=MutationDecision.NO_LEARNING,
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
