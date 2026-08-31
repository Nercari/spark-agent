from __future__ import annotations
from typing import Optional, List
from platform.learning.contracts import (
    ReflectionAnalysis,
    ReviewDecision,
    ProposedMutation,
    MutationType,
)
from platform.learning.version_store import VersionStore

class ReflectionReviewer:
    """Reviews reflection analyses to prevent duplicate or regressive mutations,
    enforce read-before-write invariants, and protect system skills."""

    def __init__(self, version_store: VersionStore):
        self.version_store = version_store
        self.protected_skills = {"system:onboarding", "system:email-writing-style", "system:workspace-tools"}

    def review_reflection(
        self,
        reflection: ReflectionAnalysis,
    ) -> ReviewDecision:
        if not reflection.has_salient_learning or not reflection.proposed_mutation:
            return ReviewDecision(
                approved=False,
                decision_reason="No salient learning or proposed mutation in reflection.",
                target_mutation=None,
            )

        mutation = reflection.proposed_mutation

        # Immutable system skill protection guardrail
        if mutation.skill_name in self.protected_skills:
            return ReviewDecision(
                approved=False,
                decision_reason=f"Skill '{mutation.skill_name}' is a protected system skill and cannot be mutated.",
                target_mutation=mutation,
            )

        # Read-before-write CAS validation
        current_version = self.version_store.get_current_version(mutation.skill_name)
        if current_version and current_version != mutation.base_version:
            return ReviewDecision(
                approved=False,
                decision_reason=f"Stale base version: proposed on '{mutation.base_version}', but current is '{current_version}'.",
                target_mutation=mutation,
            )

        # Deduplication check: verify if identical content already exists
        existing_versions = self.version_store.list_versions(mutation.skill_name)
        for v in existing_versions:
            if v.content.strip() == mutation.proposed_content.strip():
                return ReviewDecision(
                    approved=False,
                    decision_reason=f"Duplicate mutation: identical content already exists in version {v.version}.",
                    target_mutation=mutation,
                )

        return ReviewDecision(
            approved=True,
            decision_reason="Mutation approved: valid, non-duplicate, and passes version invariants.",
            target_mutation=mutation,
        )
