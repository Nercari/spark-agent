"""Hermes-compatible semantic reflection engine and subagent protocol (EXP-01, EXP-03)."""

import difflib
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from platform.learning.contracts import (
    EventType,
    EvidenceEvent,
    LearningMutation,
    MutationDecision,
    PayloadOrigin,
    ReflectionContext,
    ReflectionDecision,
    ReflectionProposal,
    SubagentAuditRecord,
    SubagentInvocationRequest,
    TaskRun,
    TrustClass,
    VerificationStatus,
    generate_sha256,
    is_untrusted_origin,
)
from platform.learning.version_store import SkillVersionStore

logger = logging.getLogger(__name__)


class DeterministicRecoveryAnalyzer:
    """Extracts causal parameter changes and recovery mechanisms between failed and successful attempts."""

    @staticmethod
    def extract_causal_rule(task_run: TaskRun) -> Optional[Tuple[str, str, List[str]]]:
        """Analyzes evidence events within a single TaskRun to extract candidate recovery rules.

        Returns (tool_name, lesson_statement, evidence_ids) or None.
        """
        error_events = [e for e in task_run.evidence_events if e.metadata.get("is_error") is True or e.event_type == EventType.TOOL_RESULT and e.metadata.get("is_error")]
        recovery_events = [e for e in task_run.evidence_events if e.metadata.get("is_recovery") is True or e.event_type == EventType.TOOL_RESULT and e.metadata.get("is_recovery")]

        if not error_events or not recovery_events:
            return None

        # Link by operation_id if present
        matched_pairs = []
        for err in error_events:
            for rec in recovery_events:
                if err.operation_id and rec.operation_id and err.operation_id == rec.operation_id:
                    matched_pairs.append((err, rec))
                elif not err.operation_id and not rec.operation_id:
                    matched_pairs.append((err, rec))

        if not matched_pairs:
            # Fallback to the latest error and recovery
            matched_pairs.append((error_events[-1], recovery_events[-1]))

        target_err, target_rec = matched_pairs[-1]

        # Extract tool params
        try:
            err_data = json.loads(target_err.content) if isinstance(target_err.content, str) else target_err.content
            rec_data = json.loads(target_rec.content) if isinstance(target_rec.content, str) else target_rec.content

            tool_name = rec_data.get("tool") or err_data.get("tool") or "tool"
            err_params = err_data.get("params", {})
            rec_params = rec_data.get("params", {})

            added_params = {}
            for k, v in rec_params.items():
                if k not in err_params or err_params[k] != v:
                    added_params[k] = v

            if not added_params:
                # Check diff summary
                diff_sum = target_rec.metadata.get("diff_summary")
                if diff_sum:
                    lesson = f"- When calling `{tool_name}`, apply fix: {diff_sum} to prevent recovery failures."
                    return tool_name, lesson, [target_err.id, target_rec.id]
                return None

            param_str = ", ".join(f"{k}={repr(v)}" for k, v in sorted(added_params.items()))
            lesson = f"- When calling `{tool_name}`, supply `{param_str}` to avoid schema validation recovery errors."
            return tool_name, lesson, [target_err.id, target_rec.id]
        except Exception as ex:
            logger.debug(f"Failed to extract causal rule: {ex}")
            return None


class SubagentReflectionParser:
    """Parses raw text or JSON response emitted by Hermes reflection subagent."""

    @staticmethod
    def parse_proposal(response_text: str, target_skill: str) -> ReflectionProposal:
        """Parses reflection output into a validated ReflectionProposal."""
        clean = response_text.strip()
        # Look for JSON block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL)
        if json_match:
            clean = json_match.group(1)

        try:
            data = json.loads(clean)
            decision = ReflectionDecision(data.get("decision", ReflectionDecision.NO_LEARNING.value))
            return ReflectionProposal(
                target_skill=target_skill,
                decision=decision,
                reason=data.get("reason", "Subagent reflection output"),
                evidence_ids=data.get("evidence_ids", []),
                proposed_procedural_lesson=data.get("proposed_procedural_lesson", ""),
                affected_section=data.get("affected_section", "## Steps"),
                recovery_verified=data.get("recovery_verified", True),
                confidence=float(data.get("confidence", 1.0)),
            )
        except Exception:
            # Fallback heuristic parser
            if "decision" in clean.lower() and "skill_patch" in clean.lower():
                lesson_match = re.search(r"proposed_procedural_lesson[\"':\s]+([^\"'\n\r]+)", clean, re.IGNORECASE)
                lesson = lesson_match.group(1).strip() if lesson_match else clean
                return ReflectionProposal(
                    target_skill=target_skill,
                    decision=ReflectionDecision.SKILL_PATCH,
                    reason="Parsed heuristic reflection output",
                    proposed_procedural_lesson=lesson,
                    recovery_verified=True,
                    confidence=0.85,
                )
            return ReflectionProposal(
                target_skill=target_skill,
                decision=ReflectionDecision.NO_LEARNING,
                reason="Subagent determined no learning required or format unparseable",
            )


class ReflectionAgentBackend(ABC):
    """Abstract interface for delegating reflection to independent subagent instances."""

    @abstractmethod
    def invoke_reflection(self, request: SubagentInvocationRequest) -> Tuple[str, str]:
        """Executes reflection subagent. Returns (raw_response_text, completion_status)."""
        pass


class MockReflectionAgentBackend(ReflectionAgentBackend):
    """Deterministic in-memory test backend simulating subagent reflection."""

    def __init__(self, canned_response: Optional[str] = None):
        self.canned_response = canned_response

    def invoke_reflection(self, request: SubagentInvocationRequest) -> Tuple[str, str]:
        if self.canned_response:
            return self.canned_response, "SUCCESS"

        # Deterministic generation
        resp = {
            "decision": ReflectionDecision.SKILL_PATCH.value,
            "reason": f"Analyzed recovery evidence for {request.target_skill}",
            "evidence_ids": request.allowed_evidence_ids,
            "proposed_procedural_lesson": f"- When running {request.target_skill}, ensure recovery verification is satisfied.",
            "affected_section": "## Steps",
            "recovery_verified": True,
            "confidence": 0.95,
        }
        return json.dumps(resp), "SUCCESS"


class DirectSubagentReflectionBackend(ReflectionAgentBackend):
    """Delegates reflection directly to Gemini subagent instance via tool protocol."""

    def __init__(self, invoke_tool_fn: Optional[Any] = None):
        self.invoke_tool_fn = invoke_tool_fn

    def invoke_reflection(self, request: SubagentInvocationRequest) -> Tuple[str, str]:
        if not self.invoke_tool_fn:
            return "", "NO_BACKEND_AVAILABLE"
        try:
            res = self.invoke_tool_fn(
                task=request.prompt,
                task_title=request.task_title,
            )
            return str(res), "SUCCESS"
        except Exception as ex:
            return str(ex), "SUBAGENT_FAILURE"


class ReflectionRuntimeBridge:
    """Constructs hermetic reflection contexts and invokes subagents with canonical digest tracking."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        backend: Optional[ReflectionAgentBackend] = None,
    ):
        self.version_store = version_store
        self.backend = backend or MockReflectionAgentBackend()
        self.audit_log: List[SubagentAuditRecord] = []

    def reflect_on_task(self, task_run: TaskRun) -> ReflectionProposal:
        """Executes subagent reflection protocol over a verified task run."""
        # 1. Verification Gate: Only reflect on verified task runs
        if task_run.verification_status != VerificationStatus.VERIFIED_SUCCESS:
            return ReflectionProposal(
                target_skill=task_run.skill_name,
                decision=ReflectionDecision.NO_LEARNING,
                reason="TaskRun was not verified as successful.",
            )

        # 2. Extract recovery and causal evidence
        causal_result = DeterministicRecoveryAnalyzer.extract_causal_rule(task_run)
        if not causal_result:
            return ReflectionProposal(
                target_skill=task_run.skill_name,
                decision=ReflectionDecision.NO_LEARNING,
                reason="No causal recovery or parameter delta identified.",
            )

        tool_name, lesson, ev_ids = causal_result

        # 3. Fetch active skill content
        skill_content = self.version_store.get_current_skill_content(task_run.skill_name)
        if not skill_content:
            return ReflectionProposal(
                target_skill=task_run.skill_name,
                decision=ReflectionDecision.NO_LEARNING,
                reason=f"Skill '{task_run.skill_name}' not found in VersionStore.",
            )

        active_ver_id = self.version_store.get_active_version_id(task_run.skill_name) or "v1"

        # 4. Build canonical reflection context & digest
        filtered_evidence = [e for e in task_run.evidence_events if e.id in ev_ids]
        context = ReflectionContext(
            task_run_id=task_run.id,
            goal=task_run.goal,
            target_skill=task_run.skill_name,
            active_skill_version=active_ver_id,
            skill_content=skill_content,
            relevant_evidence=filtered_evidence,
            verification_status=task_run.verification_status.value,
            verification_details=task_run.verification_details,
        )
        context_digest = context.compute_canonical_digest()

        # 5. Formulate Subagent Prompt
        prompt = (
            f"You are the Gemini Spark Reflection Subagent.\n"
            f"Context Digest: {context_digest}\n"
            f"Task Goal: {task_run.goal}\n"
            f"Target Skill: {task_run.skill_name} (Version: {active_ver_id})\n"
            f"Observed Recovery Rule: {lesson}\n"
            f"Relevant Evidence IDs: {ev_ids}\n\n"
            f"Formulate a structured JSON response with keys: 'decision', 'reason', 'proposed_procedural_lesson', 'confidence', 'evidence_ids'."
        )

        request = SubagentInvocationRequest(
            task_run_id=task_run.id,
            target_skill=task_run.skill_name,
            prompt=prompt,
            allowed_evidence_ids=ev_ids,
            context_digest=context_digest,
        )

        # 6. Delegate to Subagent Backend
        raw_output, status = self.backend.invoke_reflection(request)

        # 7. Parse and Validate Proposal
        proposal = SubagentReflectionParser.parse_proposal(raw_output, task_run.skill_name)
        if not proposal.proposed_procedural_lesson:
            proposal.proposed_procedural_lesson = lesson
        if not proposal.evidence_ids:
            proposal.evidence_ids = ev_ids

        # 8. Record Subagent Audit Record
        audit_record = SubagentAuditRecord(
            invocation_id=f"inv_{task_run.id}_{generate_sha256(raw_output)[:8]}",
            task_run_id=task_run.id,
            target_skill=task_run.skill_name,
            context_digest=context_digest,
            completion_status=status,
            returned_evidence_ids=proposal.evidence_ids,
            parser_result=proposal.decision.value,
        )
        self.audit_log.append(audit_record)

        return proposal


class HermesReflectionEngine:
    """Facade maintaining compatibility across single-process analyzer and subagent runtime bridge."""

    def __init__(
        self,
        version_store: SkillVersionStore,
        backend: Optional[ReflectionAgentBackend] = None,
    ):
        self.version_store = version_store
        self.bridge = ReflectionRuntimeBridge(version_store=version_store, backend=backend)

    def analyze_task_run(self, task_run: TaskRun) -> Optional[ReflectionProposal]:
        prop = self.bridge.reflect_on_task(task_run)
        if prop.decision == ReflectionDecision.NO_LEARNING:
            return None
        return prop

    def reflect_on_task(self, task_run: TaskRun) -> ReflectionProposal:
        return self.bridge.reflect_on_task(task_run)


# Backward-compatible alias
ReflectionEngine = HermesReflectionEngine
