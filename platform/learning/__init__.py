"""Gemini Spark Autonomous Learning Platform (Hermes-Compatible Baseline)."""

from platform.learning.contracts import (
    TaskRun,
    EvidenceEvent,
    SkillVersion,
    LearningMutation,
    VerificationResult,
    EventType,
    TrustClass,
    PayloadOrigin,
    VerificationStatus,
    MutationDecision,
)
from platform.learning.evidence_recorder import EvidenceRecorder
from platform.learning.verifier import OutcomeVerifier
from platform.learning.version_store import SkillVersionStore
from platform.learning.reviewer import BackgroundLearningReviewer
from platform.learning.commit_engine import LearningCommitEngine
from platform.learning.backend import (
    SkillBackend,
    LocalFilesystemSkillBackend,
    SparkRuntimeSkillBridge,
    SparkSkillUpdateManifest,
)

__all__ = [
    "TaskRun",
    "EvidenceEvent",
    "SkillVersion",
    "LearningMutation",
    "VerificationResult",
    "EventType",
    "TrustClass",
    "PayloadOrigin",
    "VerificationStatus",
    "MutationDecision",
    "EvidenceRecorder",
    "OutcomeVerifier",
    "SkillVersionStore",
    "BackgroundLearningReviewer",
    "LearningCommitEngine",
    "SkillBackend",
    "LocalFilesystemSkillBackend",
    "SparkRuntimeSkillBridge",
    "SparkSkillUpdateManifest",
]
