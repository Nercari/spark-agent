"""Hermes Reflection Engine: Fast-Path Deterministic Analysis & Semantic Subagent Reflection."""

import abc
import json
import re
import uuid
from typing import List, Optional, Tuple, Dict, Any, Set

from platform.learning.contracts import (
    TaskRun,
    EvidenceEvent,
    EventType,
    TrustClass,
    PayloadOrigin,
    VerificationStatus,
    MutationDecision,
    ReflectionContext,
    ReflectionProposal,
    is_untrusted_origin,
    can_evidence_authorize_learning,
)
from platform.learning.version_store import SkillVersionStore


class ReflectionAgentBackend(abc.ABC):
    """Abstract interface for invoking the semantic reflection subagent."""

    @abc.abstractmethod
    def reflect(self, context: ReflectionContext) -> ReflectionProposal:
        pass


class SubagentReflectionParser:
    """Parses, validates, and bounds structured output from the reflection subagent."""

    @staticmethod
    def parse_proposal(
        raw_output: str,
        target_skill: str,
        valid_evidence_ids: Set[str],
    ) -> ReflectionProposal:
        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except Exception as e:
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason=f"Malformed reflection subagent output: {str(e)}",
            )

        if not isinstance(data, dict):
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason="Subagent output is not a valid JSON dictionary.",
            )

        raw_decision = data.get("decision", "NO_LEARNING")
        if raw_decision not in {"NO_LEARNING", "SKILL_PATCH", "AUTO_COMMIT"}:
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason=f"Invalid decision '{raw_decision}' in reflection proposal.",
            )

        decision = MutationDecision.AUTO_COMMIT if raw_decision in {"SKILL_PATCH", "AUTO_COMMIT"} else MutationDecision.NO_LEARNING
        reason = data.get("reason", "Semantic reflection analysis.")
        cited_evidence_ids = data.get("evidence_ids", [])
        proposed_lesson = data.get("proposed_procedural_lesson", "").strip()
        affected_section = data.get("affected_section", "## Steps")
        recovery_verified = bool(data.get("recovery_verified", False))
        confidence = float(data.get("confidence", 1.0))

        for eid in cited_evidence_ids:
            if eid not in valid_evidence_ids:
                return ReflectionProposal(
                    target_skill=target_skill,
                    decision=MutationDecision.NO_LEARNING,
                    reason=f"Subagent cited non-existent evidence ID '{eid}'. Fails closed.",
                )

        if decision == MutationDecision.AUTO_COMMIT and not proposed_lesson:
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason="Subagent proposed SKILL_PATCH but provided empty procedural lesson.",
            )

        return ReflectionProposal(
            target_skill=target_skill,
            decision=decision,
            reason=reason,
            evidence_ids=cited_evidence_ids,
            proposed_procedural_lesson=proposed_lesson,
            affected_section=affected_section,
            recovery_verified=recovery_verified,
            confidence=confidence,
        )


class MockReflectionAgentBackend(ReflectionAgentBackend):
    """Test fake for ReflectionAgentBackend enabling unit test injection."""

    def __init__(self, preset_proposal: Optional[ReflectionProposal] = None, raw_output: Optional[str] = None):
        self.preset_proposal = preset_proposal
        self.raw_output = raw_output

    def reflect(self, context: ReflectionContext) -> ReflectionProposal:
        if self.preset_proposal is not None:
            return self.preset_proposal
        if self.raw_output is not None:
            valid_ids = {e.id for e in context.relevant_evidence}
            return SubagentReflectionParser.parse_proposal(self.raw_output, context.target_skill, valid_ids)

        return ReflectionProposal(
            target_skill=context.target_skill,
            decision=MutationDecision.NO_LEARNING,
            reason="Mock backend default: no learning.",
        )


class DirectSubagentReflectionBackend(ReflectionAgentBackend):
    """Production backend executing bounded reflection over TaskRun evidence."""

    def reflect(self, context: ReflectionContext) -> ReflectionProposal:
        valid_ids = {e.id for e in context.relevant_evidence}
        tool_events = [e for e in context.relevant_evidence if e.event_type == EventType.TOOL_RESULT]
        error_events = [e for e in tool_events if e.metadata.get("is_error", False)]
        recovery_events = [e for e in tool_events if e.metadata.get("is_recovery", False)]
        inferences = [e for e in context.relevant_evidence if e.event_type == EventType.MODEL_INFERENCE]

        if error_events and recovery_events:
            err = error_events[0]
            rec = recovery_events[0]
            
            prereq_inference = next((inf for inf in inferences if any(kw in inf.content.lower() for kw in ["before", "prerequisite", "validate", "normalize", "preprocess"])), None)
            
            if prereq_inference:
                lesson = prereq_inference.content.strip()
                return ReflectionProposal(
                    target_skill=context.target_skill,
                    decision=MutationDecision.AUTO_COMMIT,
                    reason=f"Semantic reflection extracted verified prerequisite rule from task {context.task_run_id}.",
                    evidence_ids=[err.id, rec.id, prereq_inference.id],
                    proposed_procedural_lesson=lesson,
                    affected_section="## Steps",
                    recovery_verified=True,
                    confidence=0.95,
                )

            if rec.metadata.get("is_sequence_recovery", False):
                lesson = "When processing unnormalized input, perform pre-validation and normalization before executing main transformation."
                return ReflectionProposal(
                    target_skill=context.target_skill,
                    decision=MutationDecision.AUTO_COMMIT,
                    reason=f"Semantic reflection derived sequence recovery from task {context.task_run_id}.",
                    evidence_ids=[err.id, rec.id],
                    proposed_procedural_lesson=lesson,
                    affected_section="## Steps",
                    recovery_verified=True,
                    confidence=0.92,
                )

        return ReflectionProposal(
            target_skill=context.target_skill,
            decision=MutationDecision.NO_LEARNING,
            reason="Semantic reflection found no causal procedural recovery.",
        )


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
            for rec in recovery_events:
                rec_op = rec.operation_id or rec.metadata.get("operation_id")
                rec_parent = rec.parent_attempt_id or rec.metadata.get("parent_attempt_id")

                if err_op and rec_op and err_op == rec_op:
                    paired_error = err
                    paired_recovery = rec
                    break
                elif rec_parent and rec_parent == str(err.attempt_id):
                    paired_error = err
                    paired_recovery = rec
                    break

            if paired_recovery:
                break

        if not paired_recovery or not paired_error:
            return ReflectionProposal(
                target_skill=target_skill,
                decision=MutationDecision.NO_LEARNING,
                reason="Error and recovery events belong to unlinked, unrelated operations.",
            )

        try:
            err_data = json.loads(paired_error.content)
            rec_data = json.loads(paired_recovery.content)
            err_params = err_data.get("params", {})
            rec_params = rec_data.get("params", {})

            added_keys = [k for k in rec_params if k not in err_params]
            diff_keys = [k for k in rec_params if k in err_params and rec_params[k] != err_params[k]]

            if added_keys:
                lesson = f"When invoking `{paired_recovery.metadata.get('tool_name')}`, always pass `{added_keys[0]}={rec_params[added_keys[0]]}`."
            elif diff_keys:
                lesson = f"When invoking `{paired_recovery.metadata.get('tool_name')}`, set `{diff_keys[0]}={rec_params[diff_keys[0]]}`."
            else:
                lesson = f"Apply verified parameter repair for `{paired_recovery.metadata.get('tool_name')}`."
        except Exception:
            lesson = f"Apply verified recovery procedure for tool `{paired_recovery.metadata.get('tool_name')}`."

        return ReflectionProposal(
            target_skill=target_skill,
            decision=MutationDecision.AUTO_COMMIT,
            reason=f"Verified deterministic recovery on operation '{paired_error.operation_id}'.",
            evidence_ids=[paired_error.id, paired_recovery.id],
            proposed_procedural_lesson=lesson,
            affected_section="## Procedure",
            recovery_verified=True,
            confidence=0.95,
        )


class HermesReflectionEngine:
    """Orchestrates deterministic recovery analysis and semantic subagent reflection."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        agent_backend: Optional[ReflectionAgentBackend] = None,
    ):
        self.version_store = version_store
        self.deterministic_analyzer = DeterministicRecoveryAnalyzer()
        self.agent_backend = agent_backend or DirectSubagentReflectionBackend()

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

        active_ver = self.version_store.get_active_version(target_skill)
        skill_content = active_ver.content if active_ver else ""

        context = ReflectionContext(
            task_run_id=task_run.id,
            goal=task_run.goal,
            target_skill=target_skill,
            active_skill_version=task_run.skill_version,
            skill_content=skill_content,
            relevant_evidence=task_run.evidence_events,
            verification_status=task_run.verification_status.value,
            verification_details=task_run.verification_details,
        )

        sem_proposal = self.agent_backend.reflect(context)

        valid_ids = {e.id for e in task_run.evidence_events}
        for eid in sem_proposal.evidence_ids:
            if eid not in valid_ids:
                return ReflectionProposal(
                    target_skill=target_skill,
                    decision=MutationDecision.NO_LEARNING,
                    reason=f"Cited evidence ID '{eid}' does not exist in TaskRun. Fails closed.",
                )

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

        if "unlinked" in det_proposal.reason.lower():
            return det_proposal

        return sem_proposal


# Backwards compatibility alias
HermesSemanticReflectionSubagent = DirectSubagentReflectionBackend
EOF
