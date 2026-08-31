from __future__ import annotations
import json
from typing import List, Optional, Dict, Any
from platform.learning.contracts import (
    EvidenceEvent,
    TaskExecutionRecord,
    ReflectionAnalysis,
    ProposedMutation,
    MutationType,
)

class HermesSemanticReflectionSubagent:
    """Analyzes execution traces, errors, and user corrections to generate structured reflections."""

    def analyze_execution(
        self,
        task_record: TaskExecutionRecord,
        explicit_correction: Optional[str] = None,
        untrusted_payload: Optional[str] = None,
    ) -> ReflectionAnalysis:
        # Prompt injection / untrusted web protection (EXP-01 / EXP-08)
        if untrusted_payload and any(token in untrusted_payload.lower() for token in ["ignore previous", "override", "system prompt", "exfiltrate"]):
            return ReflectionAnalysis(
                task_id=task_record.task_id,
                has_salient_learning=False,
                error_category="UNTRUSTED_INJECTION_BLOCKED",
                root_cause="Attempted prompt injection in untrusted payload.",
                is_reusable_lesson=False,
                proposed_mutation=None,
            )

        # Explicit user correction has highest priority
        if explicit_correction:
            mutation = ProposedMutation(
                skill_name=task_record.skill_name or "general",
                base_version=task_record.skill_version or "v1",
                mutation_type=MutationType.PATCH_INSTRUCTION,
                proposed_content=f"# Updated Guidelines\n- Explicit user correction: {explicit_correction}\n",
                rationale=f"Incorporated user correction: {explicit_correction}",
            )
            return ReflectionAnalysis(
                task_id=task_record.task_id,
                has_salient_learning=True,
                error_category="EXPLICIT_USER_CORRECTION",
                root_cause=explicit_correction,
                is_reusable_lesson=True,
                proposed_mutation=mutation,
            )

        # Check for recovery episodes or verification failure
        if task_record.had_recovery or task_record.verification_status == "FAILED":
            # Extract recovery parameters if present
            recovery_desc = "; ".join(task_record.error_traces) if task_record.error_traces else "Execution recovery required"
            mutation = ProposedMutation(
                skill_name=task_record.skill_name or "general",
                base_version=task_record.skill_version or "v1",
                mutation_type=MutationType.ADD_GUARDRAIL,
                proposed_content=f"# Guardrail\n- Avoid error: {recovery_desc}\n",
                rationale=f"Automated recovery analysis for {task_record.skill_name}",
            )
            return ReflectionAnalysis(
                task_id=task_record.task_id,
                has_salient_learning=True,
                error_category="EXECUTION_RECOVERY",
                root_cause=recovery_desc,
                is_reusable_lesson=True,
                proposed_mutation=mutation,
            )

        # Default: clean execution, zero mutation
        return ReflectionAnalysis(
            task_id=task_record.task_id,
            has_salient_learning=False,
            error_category="CLEAN_EXECUTION",
            root_cause="Task completed without errors or corrections.",
            is_reusable_lesson=False,
            proposed_mutation=None,
        )
