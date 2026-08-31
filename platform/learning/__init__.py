"""Autonomous Learning Platform Module Initialization."""

from platform.learning.contracts import (
    TaskRun,
    EvidenceRecord,
    TaskRunSummary,
    VerificationStatus,
    MutationDecision,
    PayloadOrigin,
    SkillVersionMetadata,
    LearningMutationProposal,
    generate_sha256,
)
from platform.learning.evidence_recorder import EvidenceRecorder
from platform.learning.verifier import OutcomeVerifier
from platform.learning.version_store import SkillVersionStore
from platform.learning.reflection import ReflectionEngine
from platform.learning.reviewer import BackgroundLearningReviewer
from platform.learning.commit_engine import LearningCommitEngine
from platform.learning.skill_router import ProceduralSkillRouter, ProceduralSkillParser, SkillManifest
from platform.learning.authority_arbiter import AuthorityArbiter, AuthorityTier, AuthorityDecision, AuthorityResolution

__all__ = [
    "TaskRun",
    "EvidenceRecord",
    "TaskRunSummary",
    "VerificationStatus",
    "MutationDecision",
    "PayloadOrigin",
    "SkillVersionMetadata",
    "LearningMutationProposal",
    "generate_sha256",
    "EvidenceRecorder",
    "OutcomeVerifier",
    "SkillVersionStore",
    "ReflectionEngine",
    "BackgroundLearningReviewer",
    "LearningCommitEngine",
    "ProceduralSkillRouter",
    "ProceduralSkillParser",
    "SkillManifest",
    "AuthorityArbiter",
    "AuthorityTier",
    "AuthorityDecision",
    "AuthorityResolution",
]
