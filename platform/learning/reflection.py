"""Hermes Reflection Engine for Experience-Driven Recovery Learning."""

import re
import json
import uuid
import difflib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from platform.learning.contracts import (
    TaskRun,
    EvidenceEvent,
    EventType,
    TrustClass,
    PayloadOrigin,
    VerificationStatus,
    LearningMutation,
    MutationDecision,
    is_untrusted_origin,
)
from platform.learning.version_store import SkillVersionStore


@dataclass
class ReflectionProposal:
    target_skill: str
    decision: MutationDecision
    reason: str
    evidence_ids: List[str] = field(default_factory=list)
    proposed_procedural_lesson: str = ""
    affected_section: str = "## Steps"
    recovery_verified: bool = False
    confidence: float = 1.0


class HermesReflectionEngine:
    """Semantic reflection engine that evaluates task execution evidence for verified recoveries."""

    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store

    def reflect_on_task(self, task_run: TaskRun) -> ReflectionProposal:
        """Inspects TaskRun evidence to classify failure/recovery and extract reusable procedural lessons."""
        target_skill = task_run.skill_name

        # 1. System Skill Guardrail
        if target_skill.startswith("system:"):
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.REJECT_SYSTEM_SKILL,
                reason="System skills are immutable and protected from autonomous reflection mutation.",
            )

        # 2. Strict Operational Payload Provenance Screening
        untrusted_events = [
            e for e in task_run.evidence_events
            if e.trust_class == TrustClass.UNTRUSTED_EXTERNAL_EVIDENCE or is_untrusted_origin(e.payload_origin)
        ]
        user_authority_events = [
            e for e in task_run.evidence_events
            if e.trust_class == TrustClass.TRUSTED_USER_AUTHORITY
        ]

        for u_ev in untrusted_events:
            content_lower = u_ev.content.lower()
            if (
                "ignore previous instructions" in content_lower
                or "from now on always" in content_lower
                or "send reports to" in content_lower
                or "exfiltrate" in content_lower
            ):
                if not user_authority_events:
                    return ReflectionProposal(
                        target_skill=target_skill,
                        decision=MutationDecision.BLOCKED_UNTRUSTED,
                        reason=f"Rejected unauthenticated behavioral directive from payload origin {u_ev.payload_origin.value}.",
                        evidence_ids=[u_ev.id],
                    )

        # 3. Analyze Tool Executions for Transient Failures
        tool_events = [e for e in task_run.evidence_events if e.event_type == EventType.TOOL_RESULT]
        error_events = [e for e in tool_events if e.metadata.get("is_error", False)]
        recovery_events = [e for e in tool_events if e.metadata.get("is_recovery", False)]

        all_transient = error_events and all(e.metadata.get("is_transient", False) for e in error_events)
        if all_transient and not recovery_events:
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason="Transient failure resolved via standard retry; no reusable procedural modification needed.",
            )

        # 4. Outcome Verification Check: Strict requirement for recovery learning
        if task_run.verification_status != VerificationStatus.VERIFIED_SUCCESS:
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason=f"Recovery learning requires VERIFIED_SUCCESS. Current verification status is {task_run.verification_status.value}.",
            )

        # 5. Check for genuine procedural failure followed by verified recovery
        non_transient_errors = [e for e in error_events if not e.metadata.get("is_transient", False)]
        if non_transient_errors and recovery_events:
            first_error = non_transient_errors[0]
            first_recovery = recovery_events[0]
            evidence_ids = [first_error.id, first_recovery.id]

            try:
                err_data = json.loads(first_error.content)
                rec_data = json.loads(first_recovery.content)
                err_params = err_data.get("params", {})
                rec_params = rec_data.get("params", {})
                
                added_keys = [k for k in rec_params if k not in err_params]
                diff_keys = [k for k in rec_params if k in err_params and rec_params[k] != err_params[k]]
                
                if added_keys:
                    lesson = f"When invoking `{first_recovery.metadata.get('tool_name')}`, always pass `{added_keys[0]}={rec_params[added_keys[0]]}` to satisfy API requirements."
                elif diff_keys:
                    lesson = f"When invoking `{first_recovery.metadata.get('tool_name')}`, set `{diff_keys[0]}={rec_params[diff_keys[0]]}`."
                else:
                    lesson = f"Use updated procedure for `{first_recovery.metadata.get('tool_name')}` as verified in task {task_run.id}."
            except Exception:
                lesson = f"Apply verified recovery procedure for tool `{first_recovery.metadata.get('tool_name')}`."

            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.AUTO_COMMIT,
                reason=f"Verified reusable recovery learned from task {task_run.id}: resolved error in `{first_error.metadata.get('tool_name')}`.",
                evidence_ids=evidence_ids,
                proposed_procedural_lesson=lesson,
                affected_section="## Procedure",
                recovery_verified=True,
                confidence=0.95,
            )

        return ReflectionProposal(
            target_skill=target_skill,
            decision=MutationDecision.NO_LEARNING,
            reason="Task execution completed without reusable failure/recovery pattern.",
        )
