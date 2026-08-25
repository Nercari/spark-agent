"""Semantic & Heuristic Classifier distinguishing Declarative Memory from Procedural Skills."""

import re
from typing import Optional
from platform.memory.contracts import (
    MemoryKind,
    MemoryScope,
    MemoryClassificationResult,
)


class MemoryClassifier:
    """Classifies user instructions and task experiences into declarative facts/preferences vs procedural skills."""

    @staticmethod
    def classify(
        text: str,
        project_scope_id: Optional[str] = None,
        user_scope_id: str = "default_user",
    ) -> MemoryClassificationResult:
        cleaned = text.strip()
        lower = cleaned.lower()

        procedural_patterns = [
            r"before\s+.*,\s*(?:always|ensure|run|execute|perform)",
            r"first\s+.*,\s*then\s+.*",
            r"workflow\s+steps",
            r"always\s+(?:run|execute|call|decompress|fetch|drain)\s+.*\s+(?:before|after)",
            r"step\s+\d+:\s*",
        ]
        for pat in procedural_patterns:
            if re.search(pat, lower):
                return MemoryClassificationResult(
                    is_memory=False,
                    is_procedural_skill=True,
                    reason="Identified multi-step procedural workflow instruction; belongs in a procedural Skill.",
                )

        pref_match = re.search(r"(?:i prefer|my preference is|i like|always format my)\s+([^.]+)", lower)
        if pref_match:
            val = pref_match.group(1).strip()
            key = "user_preference"
            if "report" in val:
                key = "report_style_preference"
            return MemoryClassificationResult(
                is_memory=True,
                kind=MemoryKind.PREFERENCE,
                scope=MemoryScope.USER,
                scope_id=user_scope_id,
                key=key,
                value=cleaned,
                reason="User expressed a personal preference; stored as user PREFERENCE memory.",
            )

        convention_match = re.search(r"(?:we call|we refer to|terminology for)\s+([^.]+)", lower)
        if convention_match and project_scope_id:
            return MemoryClassificationResult(
                is_memory=True,
                kind=MemoryKind.CONVENTION,
                scope=MemoryScope.PROJECT,
                scope_id=project_scope_id,
                key="naming_convention",
                value=cleaned,
                reason="Project naming convention detected; stored as project CONVENTION memory.",
            )

        fact_patterns = [
            (r"(?:canonical\s+export\s+format|export\s+format)\s+(?:is|to|use)?\s*[`'\"]?([a-zA-Z0-9_-]+)[`'\"]?", "canonical_export_format", MemoryKind.FACT),
            (r"(?:production|staging|deployment)\s+(?:region|zone|bucket)\s+(?:is|to)\s*[`'\"]?([a-zA-Z0-9_-]+)[`'\"]?", "deployment_environment", MemoryKind.ENVIRONMENT),
            (r"(?:use|set)\s+[`'\"]?([a-zA-Z0-9_-]+)[`'\"]?\s+as\s+(?:the\s+)?(?:canonical\s+)?export\s+format", "canonical_export_format", MemoryKind.FACT),
            (r"(?:change that —|no —|update:)?\s*this project (?:now )?uses\s+[`'\"]?([a-zA-Z0-9_-]+)[`'\"]?", "canonical_export_format", MemoryKind.CORRECTION),
        ]

        for pat, key, kind in fact_patterns:
            m = re.search(pat, lower)
            if m:
                val = m.group(1).strip()
                scope = MemoryScope.PROJECT if project_scope_id else MemoryScope.USER
                s_id = project_scope_id if project_scope_id else user_scope_id
                return MemoryClassificationResult(
                    is_memory=True,
                    kind=kind,
                    scope=scope,
                    scope_id=s_id,
                    key=key,
                    value=val,
                    reason=f"Extracted {kind.value} memory for key '{key}'.",
                )

        return MemoryClassificationResult(
            is_memory=False,
            reason="Input did not contain a durable declarative fact, preference, or convention.",
        )
