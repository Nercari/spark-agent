"""Background Learning Reviewer: Independent Evaluation & Gating of Proposed Mutations (EXP-01, EXP-03)."""

import difflib
import re
from typing import Dict, List, Optional, Tuple
from platform.learning.contracts import (
    TaskRun,
    SkillVersion,
    LearningMutation,
    ReflectionProposal,
    ReflectionDecision,
    MutationDecision,
    VerificationStatus,
    generate_sha256,
    can_evidence_authorize_learning,
)
from platform.learning.version_store import SkillVersionStore
from platform.learning.reflection import HermesReflectionEngine, ReflectionEngine


class BackgroundLearningReviewer:
    """Evaluates task runs and mutation proposals against strict authority, provenance, and causality gates."""

    def __init__(self, version_store: SkillVersionStore, reflection_engine: Optional[ReflectionEngine] = None):
        self.version_store = version_store
        self.reflection_engine = reflection_engine or HermesReflectionEngine(version_store=version_store)

    def review_task_run(self, task_run: TaskRun) -> LearningMutation:
        # System skill protection gate: System skills are immutable
        if task_run.skill_name.startswith("system:"):
            return LearningMutation(
                id="mut_sys_reject",
                task_run_id=task_run.id,
                operation="REJECT_SYSTEM_SKILL",
                target_skill=task_run.skill_name,
                base_version_id=task_run.skill_version,
                base_version_hash="",
                proposed_content="",
                diff="",
                reason="System skills are strictly immutable",
                decision=MutationDecision.REJECT_SYSTEM_SKILL,
            )

        # Verified success requirement gate
        if task_run.verification_status != VerificationStatus.VERIFIED_SUCCESS:
            return LearningMutation(
                id="mut_unverified_reject",
                task_run_id=task_run.id,
                operation="NO_LEARNING",
                target_skill=task_run.skill_name,
                base_version_id=task_run.skill_version,
                base_version_hash="",
                proposed_content="",
                diff="",
                reason="Task run did not achieve verified success",
                decision=MutationDecision.NO_LEARNING,
            )

        # Generate proposal from reflection engine
        proposal = self.reflection_engine.analyze_task_run(task_run)
        if not proposal or proposal.decision == ReflectionDecision.NO_LEARNING:
            return LearningMutation(
                id="mut_no_learning",
                task_run_id=task_run.id,
                operation="NO_LEARNING",
                target_skill=task_run.skill_name,
                base_version_id=task_run.skill_version,
                base_version_hash="",
                proposed_content="",
                diff="",
                reason="No recoverable causal evidence found in task run",
                decision=MutationDecision.NO_LEARNING,
            )

        return self.evaluate_proposal(proposal, task_run)

    def evaluate_proposal(self, proposal: ReflectionProposal, task_run: TaskRun) -> LearningMutation:
        current_content = self.version_store.get_current_skill_content(proposal.target_skill)
        if not current_content:
            return LearningMutation(
                id="mut_err",
                task_run_id=task_run.id,
                operation="NO_LEARNING",
                target_skill=proposal.target_skill,
                base_version_id=task_run.skill_version,
                base_version_hash="",
                proposed_content="",
                diff="",
                reason="Target skill not found",
                decision=MutationDecision.NO_LEARNING,
            )

        base_hash = generate_sha256(current_content)

        # Check authority & permissions
        auth_ok, auth_reason = can_evidence_authorize_learning(
            evidence_events=task_run.evidence_events,
            proposed_lesson=proposal.proposed_procedural_lesson,
            user_authorized_text=" ".join([e.content for e in task_run.evidence_events if e.event_type.value == "USER_AUTHORIZED_INSTRUCTION"]),
        )

        if not auth_ok:
            return LearningMutation(
                id="mut_blocked_auth",
                task_run_id=task_run.id,
                operation="BLOCKED_PERMISSION",
                target_skill=proposal.target_skill,
                base_version_id=task_run.skill_version,
                base_version_hash=base_hash,
                proposed_content="",
                diff="",
                reason=auth_reason,
                decision=MutationDecision.BLOCKED_PERMISSION,
                evidence_ids=proposal.evidence_ids,
            )

        # Synthesize patched content with deduplication and supersession
        updated_content, diff_str = self._patch_content(current_content, proposal.proposed_procedural_lesson)

        return LearningMutation(
            id=f"mut_{task_run.id}",
            task_run_id=task_run.id,
            operation="SKILL_PATCH",
            target_skill=proposal.target_skill,
            base_version_id=task_run.skill_version,
            base_version_hash=base_hash,
            proposed_content=updated_content,
            diff=diff_str,
            reason=proposal.reason,
            decision=MutationDecision.AUTO_COMMIT,
            evidence_ids=proposal.evidence_ids,
            recovery_verified=proposal.recovery_verified,
        )

    def _patch_content(self, current_content: str, lesson_line: str) -> Tuple[str, str]:
        if lesson_line in current_content:
            return current_content, ""

        header = "## Learned Procedural Guidelines"
        if header in current_content:
            parts = current_content.split(header)
            prefix = parts[0] + header + "\n"
            rest = parts[1].strip()

            lines = [l for l in rest.split("\n") if l.strip()]
            tool_match = re.search(r"`([^`]+)`", lesson_line)
            target_tool = tool_match.group(1) if tool_match else None

            filtered_lines = []
            for line in lines:
                is_superseded = False
                if target_tool and f"`{target_tool}`" in line:
                    is_superseded = True
                if not is_superseded:
                    filtered_lines.append(line)

            filtered_lines.append(lesson_line)
            updated_content = prefix + "\n".join(filtered_lines) + "\n"
        else:
            updated_content = (
                current_content.rstrip()
                + f"\n\n{header}\n"
                + lesson_line
                + "\n"
            )

        diff_lines = list(
            difflib.unified_diff(
                current_content.splitlines(keepends=True),
                updated_content.splitlines(keepends=True),
                fromfile="active",
                tofile="proposed",
            )
        )
        diff_str = "".join(diff_lines)
        return updated_content, diff_str
