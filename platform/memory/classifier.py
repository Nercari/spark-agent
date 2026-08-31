"""Deterministic memory classifier extracting preferences, facts, and conventions."""

import re
from typing import Optional, List, Tuple
from platform.learning.contracts import TaskRun, EvidenceEvent, EventType, TrustClass
from platform.memory.contracts import MemoryScope, MemoryKind, MemoryClassificationResult


class MemoryClassifier:
    """Classifies user communications and verified outcomes into declarative memory proposals."""

    def __init__(self):
        # Trigger patterns for declarative statements vs ephemeral task commands
        self.preference_patterns = [
            r"^(?:please\s+)?always\s+(.+)$",
            r"^i\s+(?:prefer|like|want)\s+(.+)$",
            r"^never\s+(.+)$",
            r"^from\s+now\s+on[,\s]+(.+)$",
            r"^my\s+preference\s+is\s+(.+)$",
        ]
        self.convention_patterns = [
            r"^convention:\s*(.+)$",
            r"^(?:the\s+)?project\s+standard\s+is\s+(.+)$",
            r"^format\s+all\s+(.+)\s+as\s+(.+)$",
            r"^use\s+(.+)\s+naming\s+for\s+(.+)$",
        ]
        self.fact_patterns = [
            r"^(?:note\s+that\s+)?our\s+(.+)\s+is\s+(.+)$",
            r"^the\s+(.+)\s+endpoint\s+is\s+(.+)$",
            r"^we\s+are\s+using\s+(.+)\s+version\s+(.+)$",
        ]
        self.correction_patterns = [
            r"^(?:no|incorrect|that's wrong)[,\s]+(?:we\s+use|use|it's|it is)\s+(.+)$",
            r"^don't\s+use\s+(.+)[,\s]+use\s+(.+)\s+instead$",
            r"^correction:\s*(.+)$",
        ]

    def classify_statement(
        self,
        text: str,
        active_project: Optional[str] = None,
        active_user: Optional[str] = None,
    ) -> MemoryClassificationResult:
        """Evaluates whether a text statement is a declarative memory and returns parsed metadata."""
        clean_text = text.strip()

        # Check for procedural skill instructions (starts with markdown headers or multi-step workflow)
        if clean_text.startswith("#") or "```" in clean_text or "step 1" in clean_text.lower():
            return MemoryClassificationResult(
                is_memory=False,
                reason="Content represents multi-step procedural knowledge (Skill), not declarative fact.",
                is_procedural_skill=True,
            )

        # 1. Corrections (Highest priority declarative signal)
        for pattern in self.correction_patterns:
            m = re.match(pattern, clean_text, re.IGNORECASE)
            if m:
                key, val = self._extract_key_value(m.group(0), clean_text)
                return MemoryClassificationResult(
                    is_memory=True,
                    kind=MemoryKind.CORRECTION,
                    scope=MemoryScope.PROJECT if active_project else MemoryScope.USER,
                    scope_id=active_project or active_user or "global",
                    key=key,
                    value=val,
                    reason=f"Matched correction pattern: {pattern}",
                )

        # 2. Conventions
        for pattern in self.convention_patterns:
            m = re.match(pattern, clean_text, re.IGNORECASE)
            if m:
                key, val = self._extract_key_value(m.group(0), clean_text)
                return MemoryClassificationResult(
                    is_memory=True,
                    kind=MemoryKind.CONVENTION,
                    scope=MemoryScope.PROJECT if active_project else MemoryScope.USER,
                    scope_id=active_project or active_user or "global",
                    key=key,
                    value=val,
                    reason=f"Matched convention pattern: {pattern}",
                )

        # 3. Preferences
        for pattern in self.preference_patterns:
            m = re.match(pattern, clean_text, re.IGNORECASE)
            if m:
                key, val = self._extract_key_value(m.group(0), clean_text)
                return MemoryClassificationResult(
                    is_memory=True,
                    kind=MemoryKind.PREFERENCE,
                    scope=MemoryScope.USER,
                    scope_id=active_user or "global",
                    key=key,
                    value=val,
                    reason=f"Matched user preference pattern: {pattern}",
                )

        # 4. Facts / Environment
        for pattern in self.fact_patterns:
            m = re.match(pattern, clean_text, re.IGNORECASE)
            if m:
                key, val = self._extract_key_value(m.group(0), clean_text)
                return MemoryClassificationResult(
                    is_memory=True,
                    kind=MemoryKind.FACT,
                    scope=MemoryScope.PROJECT if active_project else MemoryScope.USER,
                    scope_id=active_project or active_user or "global",
                    key=key,
                    value=val,
                    reason=f"Matched project fact pattern: {pattern}",
                )

        return MemoryClassificationResult(
            is_memory=False,
            reason="Statement does not match standing declarative memory criteria.",
        )

    def extract_from_task_events(
        self,
        task_run: TaskRun,
    ) -> List[MemoryClassificationResult]:
        """Scans TaskRun evidence for explicit user corrections and instructions."""
        proposals = []
        for ev in task_run.evidence_events:
            if ev.trust_class == TrustClass.TRUSTED_USER_AUTHORITY:
                res = self.classify_statement(
                    ev.content,
                    active_project=task_run.project_scope_id,
                    active_user=task_run.user_scope_id,
                )
                if res.is_memory:
                    proposals.append(res)
        return proposals

    def _extract_key_value(self, matched_text: str, full_text: str) -> Tuple[str, str]:
        """Normalizes free-form text into key-value pairs."""
        text = full_text.strip()
        # Common key normalization heuristics
        if "commit message" in text.lower():
            return "commit_message_format", text
        if "test runner" in text.lower() or "pytest" in text.lower() or "unittest" in text.lower():
            return "preferred_test_runner", text
        if "branch" in text.lower():
            return "branch_naming_convention", text
        if "timezone" in text.lower():
            return "default_timezone", text
        if "region" in text.lower():
            return "production_region", text
        if "format" in text.lower() or "json" in text.lower() or "yaml" in text.lower():
            return "output_format", text

        # Default clean normalized key
        words = re.findall(r"\w+", text.lower())
        key = "_".join(words[:3]) if words else "custom_convention"
        return key, text
