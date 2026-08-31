"""Background Learning Reviewer: Independent Evaluation & Gating of Proposed Mutations."""

from typing import Optional
from platform.learning.contracts import (
    TaskRun,
    LearningMutationProposal,
    MutationDecision,
    VerificationStatus,
    PayloadOrigin,
)
from platform.learning.version_store import SkillVersionStore
from platform.learning.reflection import ReflectionEngine


class BackgroundLearningReviewer:
    """Evaluates task runs and mutation proposals against strict authority, provenance, and causality gates."""

    def __init__(self, version_store: SkillVersionStore, reflection_engine: Optional[ReflectionEngine] = None):
        self.version_store = version_store
        self.reflection_engine = reflection_engine or ReflectionEngine(version_store=version_store)

    def review_task_run(self, task_run: TaskRun) -> LearningMutationProposal:
        # System skill protection gate: System skills are immutable
        if task_run.skill_name.startswith("system:"):
            return LearningMutationProposal(
                skill_name=task_run.skill_name,
                base_version_id=task_run.skill_version,
                proposed_content="",
                change_reason="System skills are strictly immutable",
                decision=MutationDecision.REJECT,
                task_run_id=task_run.id,
                confidence=0.0,
                rationale="Attempt to mutate protected system skill rejected",
            )

        # Verified success requirement gate
        if task_run.verification_status != VerificationStatus.VERIFIED_SUCCESS:
            return LearningMutationProposal(
                skill_name=task_run.skill_name,
                base_version_id=task_run.skill_version,
                proposed_content="",
                change_reason="Task run did not achieve verified success",
                decision=MutationDecision.REJECT,
                task_run_id=task_run.id,
                confidence=0.0,
                rationale="Mutations require verified successful execution",
            )

        # Generate proposal from reflection engine
        proposal = self.reflection_engine.analyze_task_run(task_run)
        if not proposal:
            return LearningMutationProposal(
                skill_name=task_run.skill_name,
                base_version_id=task_run.skill_version,
                proposed_content="",
                change_reason="No recoverable causal evidence found in task run",
                decision=MutationDecision.REJECT,
                task_run_id=task_run.id,
                confidence=0.0,
                rationale="Task execution had no recoverable error pattern",
            )

        return proposal
