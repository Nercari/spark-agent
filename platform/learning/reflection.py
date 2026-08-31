"""Hermes Semantic Reflection Engine: Causal Recovery Analysis and Subagent Reflection Protocol."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from platform.learning.contracts import (
    TaskRun,
    EvidenceEvent,
    ReflectionContext,
    ReflectionProposal,
    ReflectionDecision,
    SubagentInvocationRequest,
    SubagentAuditRecord,
    TrustClass,
    PayloadOrigin,
    VerificationStatus,
    generate_sha256,
)
from platform.learning.version_store import SkillVersionStore


class ReflectionEngine:
    """Discovers causal recovery patterns from multi-attempt task execution evidence and synthesizes skill patches."""

    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store

    def analyze_task_run(self, task_run: TaskRun) -> Optional[ReflectionProposal]:
        if task_run.verification_status != VerificationStatus.VERIFIED_SUCCESS:
            return None

        # 1. Identify failure and recovery events
        error_evs = [e for e in task_run.evidence_events if e.metadata.get("is_error")]
        recovery_evs = [e for e in task_run.evidence_events if e.metadata.get("is_recovery")]

        if not error_evs or not recovery_evs:
            return None

        last_error = error_evs[-1]
        successful_recovery = recovery_evs[-1]

        # 2. Operation Identity & Causal Linkage Check
        if last_error.operation_id and successful_recovery.operation_id:
            if last_error.operation_id != successful_recovery.operation_id:
                return None

        # 3. Disqualify untrusted payload origins from setting standing directives
        if last_error.payload_origin == PayloadOrigin.EXTERNAL_WEB or successful_recovery.payload_origin == PayloadOrigin.EXTERNAL_WEB:
            return None

        # 4. Extract parameter diff / recovery rule
        try:
            err_data = json.loads(last_error.content) if isinstance(last_error.content, str) else last_error.content
            rec_data = json.loads(successful_recovery.content) if isinstance(successful_recovery.content, str) else successful_recovery.content

            err_params = err_data.get("params", {})
            rec_params = rec_data.get("params", {})
            tool_name = rec_data.get("tool", "tool")

            added_params = {}
            for k, v in rec_params.items():
                if k not in err_params or err_params[k] != v:
                    added_params[k] = v

            if not added_params:
                return None

            param_desc = ", ".join(f"{k}={repr(v)}" for k, v in sorted(added_params.items()))
            lesson = f"- When calling `{tool_name}`, supply `{param_desc}` to prevent schema/format recovery errors."

            return ReflectionProposal(
                target_skill=task_run.skill_name,
                decision=ReflectionDecision.SKILL_PATCH,
                reason=f"Synthesized recovery procedure from task {task_run.id}",
                evidence_ids=[last_error.id, successful_recovery.id],
                proposed_procedural_lesson=lesson,
                affected_section="## Learned Procedural Guidelines",
                recovery_verified=True,
                confidence=0.95,
            )
        except Exception:
            return None

    def create_invocation_request(self, task_run: TaskRun) -> Optional[SubagentInvocationRequest]:
        current_content = self.version_store.get_current_skill_content(task_run.skill_name)
        if not current_content:
            return None

        context = ReflectionContext(
            task_run_id=task_run.id,
            goal=task_run.goal,
            target_skill=task_run.skill_name,
            active_skill_version=task_run.skill_version,
            skill_content=current_content,
            relevant_evidence=task_run.evidence_events,
            verification_status=task_run.verification_status.value,
            verification_details=task_run.verification_details,
        )

        digest = context.compute_canonical_digest()
        prompt = f"Reflect on task run {task_run.id} for skill {task_run.skill_name} and propose recovery lessons."

        return SubagentInvocationRequest(
            task_run_id=task_run.id,
            target_skill=task_run.skill_name,
            prompt=prompt,
            allowed_evidence_ids=[e.id for e in task_run.evidence_events],
            context_digest=digest,
        )
