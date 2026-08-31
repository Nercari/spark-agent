"""Core data contracts for Gemini Spark Autonomous Learning Platform (Hermes-Compatible Baseline)."""

import difflib
import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Set


class EventType(str, Enum):
    USER_AUTHORIZED_INSTRUCTION = "USER_AUTHORIZED_INSTRUCTION"
    USER_CORRECTION = "USER_CORRECTION"
    TOOL_RESULT = "TOOL_RESULT"
    EXTERNAL_CONTENT = "EXTERNAL_CONTENT"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"
    SUBAGENT_INVOCATION = "SUBAGENT_INVOCATION"
    SUBAGENT_RESULT = "SUBAGENT_RESULT"


class TrustClass(str, Enum):
    TRUSTED_USER_AUTHORITY = "TRUSTED_USER_AUTHORITY"
    INTERNAL_EXECUTION = "INTERNAL_EXECUTION"
    UNTRUSTED_EXTERNAL_EVIDENCE = "UNTRUSTED_EXTERNAL_EVIDENCE"
    VERIFICATION = "VERIFICATION"


class PayloadOrigin(str, Enum):
    LOCAL_COMPUTATION = "LOCAL_COMPUTATION"
    EXTERNAL_WEB = "EXTERNAL_WEB"
    EMAIL = "EMAIL"
    DOCUMENT = "DOCUMENT"
    MCP = "MCP"
    CONNECTED_APP = "CONNECTED_APP"
    UNKNOWN_EXTERNAL = "UNKNOWN_EXTERNAL"


def is_untrusted_origin(origin: PayloadOrigin) -> bool:
    """Returns True if the payload origin is external/untrusted by default."""
    return origin in {
        PayloadOrigin.EXTERNAL_WEB,
        PayloadOrigin.EMAIL,
        PayloadOrigin.DOCUMENT,
        PayloadOrigin.MCP,
        PayloadOrigin.CONNECTED_APP,
        PayloadOrigin.UNKNOWN_EXTERNAL,
    }


def extract_recipients_and_destinations(text: str) -> Tuple[Set[str], Set[str]]:
    """Extracts email addresses and domain names from text."""
    emails = set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text.lower()))
    urls = re.findall(r'https?://([a-zA-Z0-9-.]+)', text.lower())
    domains = set(urls)
    return emails, domains


def can_evidence_authorize_learning(
    evidence_events: List["EvidenceEvent"], proposed_lesson: str, user_authorized_text: Optional[str] = None
) -> Tuple[bool, str]:
    """Strict exact authority binding policy boundary.

    Enforces:
    1. Exact recipient & destination binding: An email or domain proposed in a lesson MUST be explicitly
       authorized in user_authorized_text. Having user authorization for boss@example.com does NOT authorize attacker@example.com.
    2. Untrusted external payloads (web, email, MCP, doc) cannot create standing behavioral directives,
       add external destinations, or grant permissions.
    """
    lesson_lower = proposed_lesson.lower()
    user_text_lower = (user_authorized_text or "").lower()

    # Rule 1: Check for general unauthorized directives
    disallowed_keywords = [
        "exfiltrate",
        "grant permission",
        "grant access",
        "disable security",
        "disable verification",
        "ignore previous instructions",
    ]
    for kw in disallowed_keywords:
        if kw in lesson_lower and kw not in user_text_lower:
            return False, f"Proposed lesson attempts to establish unauthorized directive: '{kw}'"

    # Rule 2: Exact Recipient & Destination Binding
    lesson_emails, lesson_domains = extract_recipients_and_destinations(proposed_lesson)
    user_emails, user_domains = extract_recipients_and_destinations(user_authorized_text or "")

    for email in lesson_emails:
        if email not in user_emails:
            return False, f"Unauthorized recipient '{email}' in proposed lesson. User only authorized: {list(user_emails) or 'none'}."

    for domain in lesson_domains:
        if domain not in user_domains:
            return False, f"Unauthorized domain '{domain}' in proposed lesson. User only authorized: {list(user_domains) or 'none'}."

    # Rule 3: Inspect cited evidence events for unauthenticated prompt injections
    for ev in evidence_events:
        if ev.trust_class == TrustClass.UNTRUSTED_EXTERNAL_EVIDENCE or is_untrusted_origin(ev.payload_origin):
            content_lower = ev.content.lower()
            if (
                "ignore previous instructions" in content_lower
                or "from now on always" in content_lower
                or "send reports to" in content_lower
                or "upload your files to" in content_lower
            ):
                ev_emails, ev_domains = extract_recipients_and_destinations(ev.content)
                for email in ev_emails:
                    if email in lesson_emails and email not in user_emails:
                        return False, f"Proposed lesson adopts untrusted directive for recipient '{email}' from {ev.payload_origin.value} payload."
                for domain in ev_domains:
                    if domain in lesson_domains and domain not in user_domains:
                        return False, f"Proposed lesson adopts untrusted directive for domain '{domain}' from {ev.payload_origin.value} payload."

    return True, "Evidence authorization validated."


class VerificationStatus(str, Enum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class ReflectionDecision(str, Enum):
    """Semantic proposals that a reflection subagent can emit."""
    NO_LEARNING = "NO_LEARNING"
    SKILL_PATCH = "SKILL_PATCH"
    MEMORY_CREATE = "MEMORY_CREATE"
    MEMORY_UPDATE = "MEMORY_UPDATE"


class MutationDecision(str, Enum):
    """Persistence decisions made strictly by deterministic policy."""
    AUTO_COMMIT = "AUTO_COMMIT"
    REJECT_STALE = "REJECT_STALE"
    BLOCKED_PERMISSION = "BLOCKED_PERMISSION"
    BLOCKED_UNTRUSTED = "BLOCKED_UNTRUSTED"
    REJECT_SYSTEM_SKILL = "REJECT_SYSTEM_SKILL"
    NO_LEARNING = "NO_LEARNING"


def generate_sha256(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


@dataclass
class EvidenceEvent:
    id: str
    timestamp: str
    event_type: EventType
    trust_class: TrustClass
    content: str
    payload_origin: PayloadOrigin = PayloadOrigin.UNKNOWN_EXTERNAL
    operation_id: Optional[str] = None
    attempt_id: int = 1
    parent_attempt_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["trust_class"] = self.trust_class.value
        d["payload_origin"] = self.payload_origin.value
        return d

    def content_digest(self) -> str:
        """Computes deterministic digest for evidence content & metadata."""
        canonical_str = f"{self.id}:{self.event_type.value}:{self.trust_class.value}:{self.payload_origin.value}:{self.content}:{json.dumps(self.metadata, sort_keys=True)}"
        return generate_sha256(canonical_str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceEvent":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            event_type=EventType(data["event_type"]),
            trust_class=TrustClass(data["trust_class"]),
            content=data["content"],
            payload_origin=PayloadOrigin(data.get("payload_origin", PayloadOrigin.UNKNOWN_EXTERNAL.value)),
            operation_id=data.get("operation_id"),
            attempt_id=data.get("attempt_id", 1),
            parent_attempt_id=data.get("parent_attempt_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class VerificationResult:
    status: VerificationStatus
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        return cls(
            status=VerificationStatus(data["status"]),
            reason=data["reason"],
            details=data.get("details", {}),
        )


@dataclass
class TaskRun:
    id: str
    goal: str
    started_at: str
    completed_at: str
    user_scope_id: str
    project_scope_id: str
    skill_name: str
    skill_version: str
    evidence_events: List[EvidenceEvent] = field(default_factory=list)
    final_output: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    verification_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verification_status"] = self.verification_status.value if hasattr(self.verification_status, "value") else str(self.verification_status)
        d["evidence_events"] = [e.to_dict() for e in self.evidence_events]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRun":
        events = [EvidenceEvent.from_dict(e) for e in data.get("evidence_events", [])]
        return cls(
            id=data["id"],
            goal=data["goal"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            user_scope_id=data["user_scope_id"],
            project_scope_id=data["project_scope_id"],
            skill_name=data["skill_name"],
            skill_version=data["skill_version"],
            evidence_events=events,
            final_output=data.get("final_output", ""),
            verification_status=VerificationStatus(data.get("verification_status", VerificationStatus.UNKNOWN.value)),
            verification_details=data.get("verification_details", {}),
        )


@dataclass
class SkillVersion:
    version_id: str
    skill_name: str
    parent_version_id: Optional[str]
    content: str
    content_hash: str
    created_at: str
    created_from_task_run_id: Optional[str] = None
    change_reason: str = ""
    diff: Optional[str] = None
    status: str = "active"

    def validate_diff_integrity(self, parent_version: Optional["SkillVersion"]) -> bool:
        """Validates that stored diff is exactly diff(parent_version.content, this.content)."""
        if self.parent_version_id is None or parent_version is None:
            return self.diff is None or self.diff == ""

        recomputed_lines = list(
            difflib.unified_diff(
                parent_version.content.splitlines(keepends=True),
                self.content.splitlines(keepends=True),
                fromfile=f"{self.skill_name}:{parent_version.version_id}",
                tofile=f"{self.skill_name}:{self.version_id}",
            )
        )
        recomputed_diff = "".join(recomputed_lines)
        return self.diff == recomputed_diff

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillVersion":
        return cls(**data)


@dataclass
class LearningMutation:
    id: str
    task_run_id: str
    operation: str
    target_skill: str
    base_version_id: str
    base_version_hash: str
    proposed_content: str
    diff: str
    reason: str
    decision: MutationDecision
    evidence_ids: List[str] = field(default_factory=list)
    recovery_verified: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    committed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningMutation":
        d = data.copy()
        d["decision"] = MutationDecision(d["decision"])
        return cls(**d)


@dataclass
class ReflectionContext:
    task_run_id: str
    goal: str
    target_skill: str
    active_skill_version: str
    skill_content: str
    relevant_evidence: List[EvidenceEvent]
    verification_status: str
    verification_details: Dict[str, Any] = field(default_factory=dict)

    def compute_canonical_digest(self) -> str:
        """Computes canonical digest binding the exact evidence package sent."""
        skill_content_hash = generate_sha256(self.skill_content)
        sorted_ev = sorted(self.relevant_evidence, key=lambda e: e.id)
        ev_digests = [e.content_digest() for e in sorted_ev]
        canonical_package = {
            "task_run_id": self.task_run_id,
            "goal": self.goal,
            "target_skill": self.target_skill,
            "active_skill_version": self.active_skill_version,
            "skill_content_hash": skill_content_hash,
            "verification_status": self.verification_status,
            "evidence_ids": [e.id for e in sorted_ev],
            "evidence_digests": ev_digests,
        }
        return generate_sha256(json.dumps(canonical_package, sort_keys=True))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["relevant_evidence"] = [e.to_dict() for e in self.relevant_evidence]
        return d


@dataclass
class SubagentInvocationRequest:
    task_run_id: str
    target_skill: str
    prompt: str
    allowed_evidence_ids: List[str]
    context_digest: str
    task_title: str = "Reflect on Task Recovery Evidence"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SubagentAuditRecord:
    invocation_id: str
    task_run_id: str
    target_skill: str
    context_digest: str
    completion_status: str
    returned_evidence_ids: List[str]
    parser_result: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReflectionProposal:
    target_skill: str
    decision: ReflectionDecision = ReflectionDecision.NO_LEARNING
    reason: str = ""
    evidence_ids: List[str] = field(default_factory=list)
    proposed_procedural_lesson: str = ""
    affected_section: str = "## Steps"
    recovery_verified: bool = False
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReflectionProposal":
        d = data.copy()
        d["decision"] = ReflectionDecision(d["decision"])
        return cls(**d)
