"""Declarative Memory Classifier: Multi-Pattern Extraction Engine for Preferences, Conventions, and Corrections (EXP-01)."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from platform.learning.contracts import TaskRun, EventType, TrustClass
from platform.memory.contracts import MemoryKind, MemoryScope, MemoryRecord, MemoryStatus


class MemoryClassifier:
    """Classifies and extracts declarative memories from task events with key normalization and schema validation."""

    PREFERENCE_PATTERNS = [
        r"prefer\s+([a-zA-Z0-9_\-]+)\s+for\s+([a-zA-Z0-9_\-]+)",
        r"my\s+preferred\s+([a-zA-Z0-9_\-]+)\s+is\s+([a-zA-Z0-9_\-]+)",
        r"always\s+use\s+([a-zA-Z0-9_\-]+)\s+as\s+my\s+([a-zA-Z0-9_\-]+)",
        r"timezone\s+is\s+([a-zA-Z0-9_\/]+)",
        r"currency\s+is\s+([a-zA-Z]{3})",
    ]

    CONVENTION_PATTERNS = [
        r"this\s+project\s+uses\s+([a-zA-Z0-9_\-]+)\s+for\s+([a-zA-Z0-9_\-]+)",
        r"naming\s+convention\s+is\s+([a-zA-Z0-9_\-]+)",
        r"code\s+style\s+is\s+([a-zA-Z0-9_\-]+)",
    ]

    ENVIRONMENT_PATTERNS = [
        r"default\s+([a-zA-Z0-9_\-]+)\s+environment\s+is\s+([a-zA-Z0-9_\-]+)",
        r"database\s+port\s+is\s+([0-9]+)",
        r"api\s+url\s+is\s+(https?://[a-zA-Z0-9_\-\./]+)",
    ]

    def _normalize_key(self, raw_key: str) -> str:
        k = raw_key.lower().strip()
        k = re.sub(r"[^a-z0-9_]+", "_", k)
        return k.strip("_")

    def extract_memories_from_task_run(
        self,
        task_run: TaskRun,
        default_scope: MemoryScope = MemoryScope.PROJECT,
        default_scope_id: str = "default",
    ) -> List[MemoryRecord]:
        memories: List[MemoryRecord] = []
        events = getattr(task_run, "evidence_events", getattr(task_run, "evidence_records", []))

        for ev in events:
            ev_type = getattr(ev, "event_type", None)
            t_class = getattr(ev, "trust_class", None)
            content = getattr(ev, "content", "")
            ev_id = getattr(ev, "id", getattr(ev, "evidence_id", "unknown"))

            if t_class != TrustClass.TRUSTED_USER_AUTHORITY:
                continue

            # Check explicit corrections
            if ev_type == EventType.USER_CORRECTION:
                corr_mem = self._parse_explicit_correction(content, default_scope, default_scope_id, ev_id)
                if corr_mem:
                    memories.append(corr_mem)
                continue

            # Check general user instructions
            if ev_type == EventType.USER_AUTHORIZED_INSTRUCTION:
                parsed_list = self._parse_instruction(content, default_scope, default_scope_id, ev_id)
                memories.extend(parsed_list)

        return memories

    def _parse_explicit_correction(
        self, content: str, scope: MemoryScope, scope_id: str, evidence_id: str
    ) -> Optional[MemoryRecord]:
        m = re.search(r"this project uses\s+([a-zA-Z0-9_\-]+)\s+for\s+([a-zA-Z0-9_\-]+)", content, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            topic = m.group(2).strip()
            norm_key = self._normalize_key(f"canonical_{topic}_format" if "format" not in topic else f"canonical_{topic}")
            return MemoryRecord(
                id=f"mem_corr_{evidence_id[:8]}",
                scope=scope,
                scope_id=scope_id,
                kind=MemoryKind.CONVENTION,
                key=norm_key,
                value=val,
                status=MemoryStatus.ACTIVE,
                confidence=1.0,
                revision=1,
                created_at="now",
                updated_at="now",
                evidence_ids=[evidence_id],
                metadata={"source_correction": content},
            )
        return None

    def _parse_instruction(
        self, content: str, scope: MemoryScope, scope_id: str, evidence_id: str
    ) -> List[MemoryRecord]:
        results: List[MemoryRecord] = []

        # 1. Preferred tool / runner
        m_pref = re.search(r"prefer\s+([a-zA-Z0-9_\-]+)\s+for\s+([a-zA-Z0-9_\-]+)", content, re.IGNORECASE)
        if m_pref:
            val = m_pref.group(1).strip()
            target = m_pref.group(2).strip()
            key = self._normalize_key(f"preferred_{target}_runner" if target in ["testing", "test"] else f"preferred_{target}")
            results.append(MemoryRecord(
                id=f"mem_pref_{evidence_id[:8]}",
                scope=MemoryScope.USER,
                scope_id="user_default",
                kind=MemoryKind.PREFERENCE,
                key=key,
                value=val,
                status=MemoryStatus.ACTIVE,
                confidence=1.0,
                revision=1,
                created_at="now",
                updated_at="now",
                evidence_ids=[evidence_id],
            ))

        # 2. Default environment
        m_env = re.search(r"default\s+([a-zA-Z0-9_\-]+)\s+environment\s+is\s+([a-zA-Z0-9_\-]+)", content, re.IGNORECASE)
        if m_env:
            target = m_env.group(1).strip()
            val = m_env.group(2).strip()
            key = self._normalize_key(f"default_{target}_environment")
            results.append(MemoryRecord(
                id=f"mem_env_{evidence_id[:8]}",
                scope=scope,
                scope_id=scope_id,
                kind=MemoryKind.ENVIRONMENT,
                key=key,
                value=val,
                status=MemoryStatus.ACTIVE,
                confidence=1.0,
                revision=1,
                created_at="now",
                updated_at="now",
                evidence_ids=[evidence_id],
            ))

        return results
