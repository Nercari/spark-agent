"""Enhanced Semantic Memory Classifier: Condition-Bound Convention & Correction Extraction (EXP-01)."""

import re
import uuid
from typing import List, Optional, Tuple
from platform.memory.contracts import (
    MemoryRecord,
    MemoryScope,
    MemoryKind,
    MemoryStatus,
)
from platform.learning.contracts import TaskRun


class MemoryClassifier:
    """Extracts structured declarative memory rules, project conventions, and user preferences from task runs."""

    # Explicit patterns matching project conventions, formatting rules, deployment environments, constraints, etc.
    PATTERNS = [
        # Format / schema rules: "status artifacts should use compact_json" or "uses jsonl for status"
        (r"(?:for this project|in this project|for this pilot|this project now|project|pilot)?\s*(?:status artifacts|artifacts|exports|files|output)?\s*(?:should use|uses|must use|switch to|format is)\s+([a-zA-Z0-9_-]+)", "canonical_export_format", MemoryKind.CONVENTION),
        # Default deployment environment / branch / target
        (r"(?:default|target)?\s*(?:deployment|deploy|release)\s*(?:environment|target|env)?\s*(?:is|should be|must be|to)\s+([a-zA-Z0-9_-]+)", "default_deployment_environment", MemoryKind.CONVENTION),
        # Testing framework preference: "use pytest for test runs"
        (r"(?:use|prefer)\s+([a-zA-Z0-9_-]+)\s+for\s+(?:tests|testing|test runs)", "preferred_test_runner", MemoryKind.PREFERENCE),
        # Notification recipient: "send notifications to ops@example.com"
        (r"(?:send|route)\s+(?:alerts|notifications|reports)\s+to\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", "notification_recipient", MemoryKind.FACT),
        # Style / constraint rules: "avoid verbose logging in production"
        (r"(?:avoid|do not use|disable)\s+([a-zA-Z0-9_\s-]+?)\s+(?:in|for)\s+([a-zA-Z0-9_-]+)", "negative_constraint", MemoryKind.CONVENTION),
        # User role / identity facts: "user is senior engineer"
        (r"user\s+(?:is|role is)\s+([a-zA-Z0-9_\s-]+)", "user_role", MemoryKind.FACT),
    ]

    def extract_memories_from_task_run(
        self,
        task_run: TaskRun,
        default_scope: MemoryScope = MemoryScope.PROJECT,
        scope_id: Optional[str] = None,
    ) -> List[MemoryRecord]:
        records: List[MemoryRecord] = []
        effective_scope_id = scope_id or task_run.project_scope_id or "default_project"

        # 1. Process explicit user corrections (highest priority)
        for corr in task_run.user_corrections:
            rec = self._parse_statement(
                text=corr,
                scope=default_scope,
                scope_id=effective_scope_id,
                task_run_id=task_run.id,
                confidence=1.0,
                is_correction=True,
            )
            if rec:
                records.append(rec)

        # 2. Process user instructions
        for instr in task_run.user_instructions:
            rec = self._parse_statement(
                text=instr,
                scope=default_scope,
                scope_id=effective_scope_id,
                task_run_id=task_run.id,
                confidence=0.9,
                is_correction=False,
            )
            if rec and not any(r.key == rec.key for r in records):
                records.append(rec)

        return records

    def _parse_statement(
        self,
        text: str,
        scope: MemoryScope,
        scope_id: str,
        task_run_id: str,
        confidence: float,
        is_correction: bool,
    ) -> Optional[MemoryRecord]:
        text_clean = text.strip()

        for pattern, default_key, kind in self.PATTERNS:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                key = default_key

                # Scope determination: user preferences vs project conventions
                rec_scope = scope
                rec_scope_id = scope_id
                if "prefer" in text_clean.lower() or "my" in text_clean.lower() or kind == MemoryKind.PREFERENCE:
                    rec_scope = MemoryScope.USER
                    rec_scope_id = "user_default"

                mem_id = f"mem_{uuid.uuid4().hex[:12]}"
                return MemoryRecord(
                    id=mem_id,
                    scope=rec_scope,
                    scope_id=rec_scope_id,
                    kind=kind,
                    key=key,
                    value=val,
                    status=MemoryStatus.ACTIVE,
                    confidence=confidence,
                    evidence_ids=[task_run_id],
                    metadata={
                        "raw_statement": text_clean,
                        "is_explicit_correction": is_correction,
                    },
                )

        return None
