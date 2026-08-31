from __future__ import annotations
from typing import Optional, Dict, Any
from platform.learning.contracts import ProposedMutation, ReviewDecision, VerificationResult
from platform.learning.backend import SkillBackend

class LearningCommitEngine:
    """Applies verified skill mutations atomically with CAS versioning."""

    def __init__(self, backend: SkillBackend):
        self.backend = backend

    def commit_mutation(
        self,
        mutation: ProposedMutation,
        verification: VerificationResult,
    ) -> bool:
        if not verification.passed:
            return False

        # Apply update to skill backend
        return self.backend.apply_mutation(
            skill_name=mutation.skill_name,
            expected_base_version=mutation.base_version,
            new_content=mutation.proposed_content,
            commit_message=mutation.rationale,
        )
