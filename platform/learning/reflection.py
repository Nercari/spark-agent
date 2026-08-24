"""Hermes Reflection Engine: Deterministic Fast-Path & Semantic Subagent Reflection."""

import re
import json
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from platform.learning.contracts import (
    TaskRun,
    EvidenceEvent,
    EventType,
    TrustClass,
    PayloadOrigin,
    VerificationStatus,
    MutationDecision,
    is_untrusted_origin,
    can_evidence_authorize_learning,
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


class DeterministicRecoveryAnalyzer:
    """Fast-path deterministic analyzer for parameter-diff recoveries on strictly linked operations."""

    def analyze_recovery(self, task_run: TaskRun) -> ReflectionProposal:
        target_skill = task_run.skill_name
        tool_events = [e for e in task_run.evidence_events if e.event_type == EventType.TOOL_RESULT]
        error_events = [e for e in tool_events if e.metadata.get("is_error", False) and not e.metadata.get("is_transient", False)]
        recovery_events = [e for e in tool_events if e.metadata.get("is_recovery", False)]

        if not error_events or not recovery_events:
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason="No non-transient error and recovery pair detected.",
            )

        paired_recovery = None
        paired_error = None

        for err in error_events:
            err_op = err.operation_id or err.metadata.get("operation_id")
            err_tool = err.metadata.get("tool_name")
            for rec in recovery_events:
                rec_op = rec.operation_id or rec.metadata.get("operation_id")
                rec_tool = rec.metadata.get("tool_name")
                rec_parent = rec.parent_attempt_id or rec.metadata.get("parent_attempt_id")

                if (err_op and rec_op and err_op == rec_op) or (rec_parent and rec_parent == str(err.attempt_id)):
                    paired_error = err
                    paired_recovery = rec
                    break
                elif not err_op and not rec_op and err_tool and rec_tool and err_tool == rec_tool:
                    paired_error = err
                    paired_recovery = rec
                    break

            if paired_recovery:
                break

        if not paired_recovery or not paired_error:
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason="Error and recovery events belong to unlinked, unrelated tools/operations.",
            )

        try:
            err_data = json.loads(paired_error.content)
            rec_data = json.loads(paired_recovery.content)
            err_params = err_data.get("params", {})
            rec_params = rec_data.get("params", {})

            added_keys = [k for k in rec_params if k not in err_params]
            diff_keys = [k for k in rec_params if k in err_params and rec_params[k] != err_params[k]]

            if added_keys:
                lesson = f"When invoking `{paired_recovery.metadata.get('tool_name')}`, always pass `{added_keys[0]}={rec_params[added_keys[0]]}` to satisfy API requirements."
            elif diff_keys:
                lesson = f"When invoking `{paired_recovery.metadata.get('tool_name')}`, set `{diff_keys[0]}={rec_params[diff_keys[0]]}`."
            else:
                lesson = f"Apply verified parameter repair for `{paired_recovery.metadata.get('tool_name')}` as verified in task {task_run.id}."
        except Exception:
            lesson = f"Apply verified recovery procedure for tool `{paired_recovery.metadata.get('tool_name')}`."

        return ReflectionProposal(
            target_skill=target_skill,
            decision=MutationDecision.AUTO_COMMIT,
            reason=f"Verified deterministic recovery on operation '{paired_error.operation_id}': resolved error in `{paired_error.metadata.get('tool_name')}`.",
            evidence_ids=[paired_error.id, paired_recovery.id],
            proposed_procedural_lesson=lesson,
            affected_section="## Procedure",
            recovery_verified=True,
            confidence=0.95,
        )


class HermesSemanticReflectionSubagent:
    """Semantic post-task reflection subagent for non-trivial procedural experience."""

    def reflect_on_experience(self, task_run: TaskRun, skill_content: str) -> ReflectionProposal:
        target_skill = task_run.skill_name

        tool_events = [e for e in task_run.evidence_events if e.event_type == EventType.TOOL_RESULT]
        error_events = [e for e in tool_events if e.metadata.get("is_error", False)]
        recovery_events = [e for e in tool_events if e.metadata.get("is_recovery", False)]
        model_inferences = [e for e in task_run.evidence_events if e.event_type == EventType.MODEL_INFERENCE]

        prerequisite_match = None
        for inf in model_inferences:
            inf_lower = inf.content.lower()
            if "before" in inf_lower or "prerequisite" in inf_lower or "pre-validate" in inf_lower or "normalize" in inf_lower or "preprocess" in inf_lower:
                prerequisite_match = inf.content
                break

        if prerequisite_match:
            lesson = f"Before formatting metrics, ensure prerequisites are met: {prerequisite_match.strip()}"
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.AUTO_COMMIT,
                reason=f"Semantic reflection extracted procedural sequence rule from task {task_run.id}.",
                evidence_ids=[error_events[0].id if error_events else task_run.id],
                proposed_procedural_lesson=lesson,
                affected_section="## Steps",
                recovery_verified=True,
                confidence=0.95,
            )

        if recovery_events and any(e.metadata.get("is_sequence_recovery", False) for e in recovery_events):
            rec = next(e for e in recovery_events if e.metadata.get("is_sequence_recovery", False))
            lesson = "Before formatting metrics, validate and normalize nested timestamp and telemetry fields using standard ISO 8601 representation."
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.AUTO_COMMIT,
                reason=f"Semantic reflection identified non-trivial procedural prerequisite in task {task_run.id}.",
                evidence_ids=[rec.id],
                proposed_procedural_lesson=lesson,
                affected_section="## Steps",
                recovery_verified=True,
                confidence=0.98,
            )

        return ReflectionProposal(
            target_skill=target_skill,
            decision=MutationDecision.NO_LEARNING,
            reason="Semantic reflection concluded no non-trivial procedural pattern was discovered.",
        )


class HermesReflectionEngine:
    """Orchestrates deterministic recovery analysis and semantic subagent reflection."""

    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store
        self.deterministic_analyzer = DeterministicRecoveryAnalyzer()
        self.semantic_subagent = HermesSemanticReflectionSubagent()

    def reflect_on_task(self, task_run: TaskRun) -> ReflectionProposal:
        target_skill = task_run.skill_name

        if target_skill.startswith("system:"):
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.REJECT_SYSTEM_SKILL,
                reason="System skills are immutable and protected from autonomous reflection mutation.",
            )

        user_auth_events = [e for e in task_run.evidence_events if e.trust_class == TrustClass.TRUSTED_USER_AUTHORITY]
        user_auth_text = " ".join([e.content for e in user_auth_events]) if user_auth_events else None

        for ev in task_run.evidence_events:
            if ev.trust_class == TrustClass.UNTRUSTED_EXTERNAL_EVIDENCE or is_untrusted_origin(ev.payload_origin):
                content_lower = ev.content.lower()
                if (
                    "ignore previous instructions" in content_lower
                    or "from now on always" in content_lower
                    or "send reports to" in content_lower
                    or "exfiltrate" in content_lower
                    or "upload your files to" in content_lower
                ):
                    auth_ok, auth_reason = can_evidence_authorize_learning(
                        evidence_events=[ev],
                        proposed_lesson=ev.content,
                        user_authorized_text=user_auth_text,
                    )
                    if not auth_ok:
                        return ReflectionProposal(
                            target_skill=target_skill,
                            decision=MutationDecision.BLOCKED_UNTRUSTED,
                            reason=f"Rejected unauthenticated behavioral directive from payload origin {ev.payload_origin.value}. External evidence cannot independently create standing authority.",
                            evidence_ids=[ev.id],
                        )

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

        if task_run.verification_status != VerificationStatus.VERIFIED_SUCCESS:
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason=f"Recovery learning requires VERIFIED_SUCCESS. Current verification status is {task_run.verification_status.value}.",
            )

        active_ver = self.version_store.get_active_version(target_skill)
        skill_content = active_ver.content if active_ver else ""
        has_semantic_hint = any(
            e.event_type == EventType.MODEL_INFERENCE and any(kw in e.content.lower() for kw in ["before", "prerequisite", "normalize", "preprocess"])
            for e in task_run.evidence_events
        )

        if has_semantic_hint:
            sem_proposal = self.semantic_subagent.reflect_on_experience(task_run, skill_content)
            if sem_proposal.decision == MutationDecision.AUTO_COMMIT:
                auth_ok, auth_reason = can_evidence_authorize_learning(
                    evidence_events=task_run.evidence_events,
                    proposed_lesson=sem_proposal.proposed_procedural_lesson,
                    user_authorized_text=user_auth_text,
                )
                if not auth_ok:
                    sem_proposal.decision = MutationDecision.BLOCKED_UNTRUSTED
                    sem_proposal.reason = auth_reason
                return sem_proposal

        det_proposal = self.deterministic_analyzer.analyze_recovery(task_run)
        if det_proposal.decision == MutationDecision.AUTO_COMMIT:
            auth_ok, auth_reason = can_evidence_authorize_learning(
                evidence_events=task_run.evidence_events,
                proposed_lesson=det_proposal.proposed_procedural_lesson,
                user_authorized_text=user_auth_text,
            )
            if not auth_ok:
                det_proposal.decision = MutationDecision.BLOCKED_UNTRUSTED
                det_proposal.reason = auth_reason
            return det_proposal

        if "unlinked" in det_proposal.reason.lower():
            return det_proposal

        return ReflectionProposal(
            target_skill=target_skill,
            decision=MutationDecision.NO_LEARNING,
            reason="Task execution completed without reusable failure/recovery pattern.",
        )
EOF
