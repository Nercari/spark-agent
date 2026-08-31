"""Adaptive Multi-Source Authority Arbiter & Conflict-Resolution Engine (EXP-08).

Enforces strict 4-tier hierarchy:
Tier 1: Current Authoritative State (live remote API / verified environment reality)
Tier 2: Active Declarative Convention (memory.json / MemoryStore)
Tier 3: Applicable Procedural Skill (SKILL.md / SkillVersionStore)
Tier 4: Episodic Historical Evidence (episodes.json / EpisodicRetriever)
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from platform.learning.contracts import VerificationStatus
from platform.memory.contracts import MemoryRecord, MemoryScope, MemoryStatus


class AuthorityTier(int, Enum):
    LIVE_STATE = 1
    DECLARATIVE_CONVENTION = 2
    PROCEDURAL_SKILL = 3
    EPISODIC_EVIDENCE = 4


class AuthorityDecision(str, Enum):
    ACCEPT = "ACCEPT"
    OVERRIDE = "OVERRIDE"
    DISQUALIFY = "DISQUALIFY"
    WARN_STALE = "WARN_STALE"


@dataclass
class AuthorityCandidate:
    tier: AuthorityTier
    source_name: str
    key: str
    value: Any
    scope: Optional[MemoryScope] = None
    scope_id: Optional[str] = None
    confidence: float = 1.0
    is_trusted_origin: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArbitrationResult:
    key: str
    winning_value: Any
    winning_candidate: AuthorityCandidate
    decision: AuthorityDecision
    reason: str
    disqualified_candidates: List[AuthorityCandidate] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# Alias for backward compatibility
AuthorityResolution = ArbitrationResult


class AuthorityArbiter:
    """Arbiter that deterministically resolves conflicts between live state, declarative conventions, procedural skills, and episodic history."""

    @staticmethod
    def resolve_candidate_conflict(
        key: str,
        candidates: List[AuthorityCandidate],
    ) -> ArbitrationResult:
        if not candidates:
            raise ValueError(f"Cannot resolve authority without candidates for key {key}")

        disqualified: List[AuthorityCandidate] = []
        warnings: List[str] = []
        eligible: List[AuthorityCandidate] = []

        # 1. Untrusted Origin Disqualification Gate
        for cand in candidates:
            if not cand.is_trusted_origin and cand.tier != AuthorityTier.LIVE_STATE:
                disqualified.append(cand)
            else:
                eligible.append(cand)

        if not eligible:
            raise ValueError(f"All candidates disqualified for key {key}")

        # 2. Sort by Tier (Tier 1 > Tier 2 > Tier 3 > Tier 4)
        def sort_key(c: AuthorityCandidate) -> Tuple[int, int, float]:
            tier_val = c.tier.value
            # Scope tie-breaker within same tier (Project > User)
            scope_val = 0
            if c.scope == MemoryScope.PROJECT:
                scope_val = -1
            elif c.scope == MemoryScope.USER:
                scope_val = 1
            return (tier_val, scope_val, -c.confidence)

        eligible.sort(key=sort_key)
        winner = eligible[0]

        # 3. Detect and warn on overridden lower-tier candidates
        for lower in eligible[1:]:
            if lower.value != winner.value:
                warnings.append(
                    f"Candidate from {lower.source_name} (Tier {lower.tier.name}, value={lower.value}) "
                    f"was overridden by authoritative {winner.source_name} (Tier {winner.tier.name}, value={winner.value})."
                )

        reason = f"Candidate from {winner.source_name} selected as highest authority (Tier {winner.tier.name})."

        return ArbitrationResult(
            key=key,
            winning_value=winner.value,
            winning_candidate=winner,
            decision=AuthorityDecision.ACCEPT,
            reason=reason,
            disqualified_candidates=disqualified,
            warnings=warnings,
        )

    @staticmethod
    def arbitrate_task_parameter(
        param_name: str,
        live_value: Optional[Any] = None,
        active_convention_value: Optional[Any] = None,
        convention_scope: Optional[MemoryScope] = None,
        skill_guideline_value: Optional[Any] = None,
        episodic_observed_value: Optional[Any] = None,
        external_untrusted_claim: Optional[Any] = None,
    ) -> ArbitrationResult:
        candidates: List[AuthorityCandidate] = []

        if live_value is not None:
            candidates.append(AuthorityCandidate(
                tier=AuthorityTier.LIVE_STATE,
                source_name="live_authoritative_state",
                key=param_name,
                value=live_value,
                confidence=1.0,
                is_trusted_origin=True,
            ))

        if active_convention_value is not None:
            candidates.append(AuthorityCandidate(
                tier=AuthorityTier.DECLARATIVE_CONVENTION,
                source_name="active_declarative_convention",
                key=param_name,
                value=active_convention_value,
                scope=convention_scope or MemoryScope.PROJECT,
                confidence=1.0,
                is_trusted_origin=True,
            ))

        if skill_guideline_value is not None:
            candidates.append(AuthorityCandidate(
                tier=AuthorityTier.PROCEDURAL_SKILL,
                source_name="procedural_skill_guideline",
                key=param_name,
                value=skill_guideline_value,
                confidence=0.9,
                is_trusted_origin=True,
            ))

        if episodic_observed_value is not None:
            candidates.append(AuthorityCandidate(
                tier=AuthorityTier.EPISODIC_EVIDENCE,
                source_name="episodic_historical_evidence",
                key=param_name,
                value=episodic_observed_value,
                confidence=0.8,
                is_trusted_origin=True,
            ))

        if external_untrusted_claim is not None:
            candidates.append(AuthorityCandidate(
                tier=AuthorityTier.DECLARATIVE_CONVENTION,
                source_name="untrusted_external_claim",
                key=param_name,
                value=external_untrusted_claim,
                confidence=0.1,
                is_trusted_origin=False,
            ))

        return AuthorityArbiter.resolve_candidate_conflict(param_name, candidates)

    @staticmethod
    def sanitize_context_against_authority(
        injected_memories: List[MemoryRecord],
        retrieved_episodes: List[Any],
    ) -> List[str]:
        """Detects contradictions between authoritative declarative memories and historical episodic records, adding warning annotations."""
        annotations = []
        mem_map = {m.key: m.value for m in injected_memories if m.status == MemoryStatus.ACTIVE}

        for ep in retrieved_episodes:
            ep_recovery = getattr(ep, "recovery", None) or {}
            ep_params = ep_recovery.get("params", {}) if isinstance(ep_recovery, dict) else {}
            for k, v in ep_params.items():
                if k in mem_map and mem_map[k] != v:
                    annotations.append(
                        f"AUTHORITY WARNING: Retrieved episode {getattr(ep, 'task_run_id', 'unknown')} contains historical parameter "
                        f"`{k}={v}`, but active authoritative convention specifies `{k}={mem_map[k]}`. Standing convention takes precedence."
                    )

        return annotations
