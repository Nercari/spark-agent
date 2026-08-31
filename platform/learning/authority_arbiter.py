from __future__ import annotations
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from platform.memory.contracts import DeclarativeMemoryRecord, MemoryScope

class AuthorityTier(IntEnum):
    TIER_1_LIVE_STATE = 1
    TIER_2_DECLARATIVE_CONVENTION = 2
    TIER_3_PROCEDURAL_SKILL = 3
    TIER_4_EPISODIC_EVIDENCE = 4

@dataclass
class AuthorityDecision:
    winning_tier: AuthorityTier
    effective_value: Any
    rationale: str
    overridden_candidates: List[Dict[str, Any]]

@dataclass
class AuthorityResolution:
    resolved_parameter: str
    value: Any
    tier: AuthorityTier
    scope: str
    annotated_warnings: List[str]

class AuthorityArbiter:
    """Arbiter resolving conflicting directives according to the 4-tier authority hierarchy:
    Tier 1 (Live State / Real-Time Tool Results) >
    Tier 2 (Declarative Conventions & Constraints) >
    Tier 3 (Procedural Skill Instructions) >
    Tier 4 (Episodic Evidence & Historical Heuristics).
    """

    def arbitrate_candidates(
        self,
        parameter_name: str,
        candidates: List[Dict[str, Any]],
        project_scope: Optional[str] = None,
    ) -> AuthorityDecision:
        if not candidates:
            raise ValueError("Candidates list cannot be empty")

        # Disqualify untrusted external candidates attempting to override higher tiers
        valid_candidates = [
            c for c in candidates
            if not c.get("untrusted_source", False)
        ]
        if not valid_candidates:
            # All candidates untrusted
            return AuthorityDecision(
                winning_tier=AuthorityTier.TIER_2_DECLARATIVE_CONVENTION,
                effective_value=None,
                rationale="All proposed candidates were untrusted and disqualified.",
                overridden_candidates=candidates,
            )

        # Sort primarily by tier (lowest integer = highest authority)
        # Secondarily by scope (PROJECT > USER) for Tier 2
        def sort_key(c: Dict[str, Any]):
            tier = c.get("tier", AuthorityTier.TIER_4_EPISODIC_EVIDENCE)
            scope = c.get("scope", "USER")
            scope_score = 0 if scope == "PROJECT" else 1
            return (int(tier), scope_score)

        valid_candidates.sort(key=sort_key)
        winner = valid_candidates[0]
        overridden = [c for c in candidates if c != winner]

        return AuthorityDecision(
            winning_tier=winner.get("tier", AuthorityTier.TIER_4_EPISODIC_EVIDENCE),
            effective_value=winner.get("value"),
            rationale=f"Selected candidate from Tier {winner.get('tier')} ({winner.get('scope', 'USER')} scope).",
            overridden_candidates=overridden,
        )

    def sanitize_context_against_authority(
        self,
        historical_episodes: List[Dict[str, Any]],
        active_conventions: List[DeclarativeMemoryRecord],
    ) -> List[Dict[str, Any]]:
        """Annotates historical episodes with AUTHORITY WARNING if they use outdated parameters."""
        sanitized = []
        convention_map = {c.content.split(":")[0].strip().lower(): c.content for c in active_conventions}

        for ep in historical_episodes:
            ep_copy = dict(ep)
            for k, conv_text in convention_map.items():
                if k in ep.get("parameters", {}):
                    # Annotate warning if different
                    ep_copy["authority_warning"] = f"AUTHORITY WARNING: Stale parameter overridden by active convention '{conv_text}'"
            sanitized.append(ep_copy)
        return sanitized
