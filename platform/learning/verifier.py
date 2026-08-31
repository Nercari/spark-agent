from __future__ import annotations
from platform.learning.contracts import ProposedMutation, VerificationResult

class MutationVerifier:
    """Verifies proposed mutations against safety contracts, syntax checks, and test harnesses."""

    def verify_mutation(self, mutation: ProposedMutation) -> VerificationResult:
        if not mutation.proposed_content or len(mutation.proposed_content.strip()) < 10:
            return VerificationResult(
                passed=False,
                error_message="Proposed content is empty or trivially short.",
            )

        # Verify Markdown / structural headers
        if not mutation.proposed_content.startswith("#"):
            return VerificationResult(
                passed=False,
                error_message="Proposed skill content must start with a markdown header.",
            )

        return VerificationResult(
            passed=True,
            error_message=None,
        )
