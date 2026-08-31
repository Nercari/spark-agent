"""Hermes Semantic Reflection Engine: Multi-Attempt Causal Discovery & Deterministic Recovery Synthesis."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from platform.learning.contracts import (
    TaskRun,
    EvidenceRecord,
    LearningMutationProposal,
    MutationDecision,
    PayloadOrigin,
    VerificationStatus,
    generate_sha256,
)
from platform.learning.version_store import SkillVersionStore


class ReflectionEngine:
    """Discovers causal recovery patterns from multi-attempt task execution evidence and synthesizes skill patches."""

    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store

    def analyze_task_run(self, task_run: TaskRun) -> Optional[LearningMutationProposal]:
        if not task_run.has_recovery():
            return None

        # 1. Authority & Success Verification Gate
        if task_run.verification_status != VerificationStatus.VERIFIED_SUCCESS:
            return None

        # 2. Extract failed attempts and matching recovery attempt
        error_evs = [e for e in task_run.evidence_records if e.is_error]
        recovery_evs = [e for e in task_run.evidence_records if e.is_recovery]

        if not error_evs or not recovery_evs:
            return None

        last_error = error_evs[-1]
        successful_recovery = recovery_evs[-1]

        # 3. Operation Identity & Causal Linkage Check
        if last_error.operation_id and successful_recovery.operation_id:
            if last_error.operation_id != successful_recovery.operation_id:
                return None

        # 4. Untrusted Payload Origin Disqualification Gate
        if last_error.payload_origin == PayloadOrigin.EXTERNAL_DATA or successful_recovery.payload_origin == PayloadOrigin.EXTERNAL_DATA:
            return None

        # 5. Extract parameter diff / recovery rule
        recovery_rule = self._extract_recovery_rule(last_error, successful_recovery)
        if not recovery_rule:
            return None

        current_content = self.version_store.get_current_skill_content(task_run.skill_name)
        if not current_content:
            return None

        # 6. Synthesize Updated Skill Content with Deduplicating Patching (EXP-03)
        updated_content, diff_str = self._patch_skill_content(
            current_content=current_content,
            recovery_rule=recovery_rule,
            tool_name=successful_recovery.tool_name,
        )

        return LearningMutationProposal(
            skill_name=task_run.skill_name,
            base_version_id=task_run.skill_version,
            proposed_content=updated_content,
            change_reason=f"Synthesized recovery procedure from verified recovery in task {task_run.id}",
            decision=MutationDecision.AUTO_COMMIT,
            task_run_id=task_run.id,
            evidence_ids=[last_error.evidence_id, successful_recovery.evidence_id],
            confidence=0.95,
            rationale=f"Observed error on attempt {last_error.attempt_id} succeeded on recovery attempt {successful_recovery.attempt_id} with {recovery_rule}",
            unified_diff=diff_str,
        )

    def _extract_recovery_rule(self, err_ev: EvidenceRecord, rec_ev: EvidenceRecord) -> Optional[Dict[str, Any]]:
        err_params = err_ev.params or {}
        rec_params = rec_ev.params or {}

        added_params = {}
        for k, v in rec_params.items():
            if k not in err_params or err_params[k] != v:
                added_params[k] = v

        if not added_params:
            return None

        return {
            "parameter_diff": added_params,
            "error_summary": err_ev.result.get("error", "Operation failed"),
            "tool_name": rec_ev.tool_name,
        }

    def _patch_skill_content(
        self,
        current_content: str,
        recovery_rule: Dict[str, Any],
        tool_name: str,
    ) -> Tuple[str, str]:
        param_diff = recovery_rule.get("parameter_diff", {})
        param_desc = ", ".join(f"{k}={repr(v)}" for k, v in sorted(param_diff.items()))

        guideline_line = f"- When calling `{tool_name}`, supply `{param_desc}` to prevent schema/format recovery errors."

        # Deduplication check: if guideline already exists, don't duplicate
        if guideline_line in current_content:
            return current_content, ""

        if "## Learned Procedural Guidelines" in current_content:
            parts = current_content.split("## Learned Procedural Guidelines")
            header = parts[0] + "## Learned Procedural Guidelines\n"
            rest = parts[1].strip()

            # Supersede any older guideline for the same tool and parameter keys
            lines = [l for l in rest.split("\n") if l.strip()]
            filtered_lines = []
            for line in lines:
                is_stale_for_tool = False
                if f"`{tool_name}`" in line:
                    for k in param_diff.keys():
                        if f"`{k}=" in line:
                            is_stale_for_tool = True
                            break
                if not is_stale_for_tool:
                    filtered_lines.append(line)

            filtered_lines.append(guideline_line)
            updated_section = "\n".join(filtered_lines) + "\n"
            updated_content = header + updated_section
        else:
            updated_content = (
                current_content.rstrip()
                + "\n\n## Learned Procedural Guidelines\n"
                + guideline_line
                + "\n"
            )

        diff_str = f"--- active\n+++ proposed\n@@\n+{guideline_line}\n"
        return updated_content, diff_str
