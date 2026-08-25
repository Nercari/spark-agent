"""Durable Declarative Memory Store with Scope Isolation, Versioning, and Authority-Aware Writes."""

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from platform.memory.contracts import (
    MemoryRecord,
    MemoryScope,
    MemoryKind,
    MemoryStatus,
)
from platform.memory.backend import (
    MemoryBackend,
    LocalFilesystemMemoryBackend,
    DurableSparkMemoryBackend,
)


class MemoryStore:
    """Manages persistent declarative memories with authority enforcement and revision protection."""

    def __init__(
        self,
        backend: Optional[MemoryBackend] = None,
        base_storage_dir: Optional[str] = None,
    ):
        if backend:
            self.backend = backend
        elif base_storage_dir:
            self.backend = LocalFilesystemMemoryBackend(base_dir=base_storage_dir)
        else:
            self.backend = DurableSparkMemoryBackend()

    def get_memory(self, record_id: str) -> Optional[MemoryRecord]:
        return self.backend.get(record_id)

    def create_or_update_memory(
        self,
        scope: MemoryScope,
        scope_id: str,
        kind: MemoryKind,
        key: str,
        value: Any,
        provenance_evidence_ids: List[str],
        is_trusted_user_authority: bool = True,
        expected_revision: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[MemoryRecord], Optional[MemoryRecord], bool, str]:
        """Authority-aware creation and supersession of memory records.

        Returns: (new_record, superseded_record, success, message)
        """
        normalized_key = key.strip().lower().replace(" ", "_")

        existing_records = self.retrieve_memories(
            scope=scope,
            scope_id=scope_id,
            key=normalized_key,
            status=MemoryStatus.ACTIVE,
        )

        superseded_record: Optional[MemoryRecord] = None
        supersedes_id: Optional[str] = None

        if existing_records:
            active_mem = existing_records[0]
            # Part 5: Unauthorized external writes cannot overwrite active user memory
            if not is_trusted_user_authority:
                conflicts = active_mem.metadata.setdefault("candidate_conflicts", [])
                conflicts.append({
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "untrusted_value": value,
                    "provenance": provenance_evidence_ids,
                })
                self.backend.update(active_mem)
                return active_mem, None, False, f"Unauthorized external evidence cannot overwrite active user memory for '{normalized_key}'."

            # Part 6: Lightweight revision protection
            current_rev = active_mem.metadata.get("revision")
            if expected_revision and current_rev != expected_revision:
                return None, None, False, f"Stale-write race on key '{normalized_key}': expected revision {expected_revision}, got {current_rev}."

            superseded_record = active_mem
            supersedes_id = superseded_record.id
            superseded_record.status = MemoryStatus.SUPERSEDED
            superseded_record.metadata["superseded_at"] = datetime.now(timezone.utc).isoformat()
            self.backend.update(superseded_record)

        now_iso = datetime.now(timezone.utc).isoformat()
        meta = metadata or {}
        meta["revision"] = f"rev_{uuid.uuid4().hex[:8]}"

        new_record = MemoryRecord(
            id=f"mem_{uuid.uuid4().hex[:10]}",
            scope=scope,
            scope_id=scope_id,
            kind=kind,
            key=normalized_key,
            value=value,
            provenance_evidence_ids=provenance_evidence_ids,
            created_at=now_iso,
            last_confirmed_at=now_iso,
            status=MemoryStatus.ACTIVE,
            supersedes_memory_id=supersedes_id,
            metadata=meta,
        )
        self.backend.put(new_record)
        return new_record, superseded_record, True, "Memory persisted successfully."

    def handle_external_conflict(
        self,
        scope: MemoryScope,
        scope_id: str,
        key: str,
        external_value: Any,
        source_evidence_id: str,
        source_ref: str = "",
    ) -> Tuple[bool, str, Optional[MemoryRecord]]:
        """Safely logs conflicting external evidence without mutating active user truth."""
        normalized_key = key.strip().lower().replace(" ", "_")
        existing_records = self.retrieve_memories(
            scope=scope,
            scope_id=scope_id,
            key=normalized_key,
            status=MemoryStatus.ACTIVE,
        )

        if not existing_records:
            return False, "No existing user memory to conflict with.", None

        active_mem = existing_records[0]
        if active_mem.value == external_value:
            return False, "External value matches active memory; no conflict.", active_mem

        conflicts = active_mem.metadata.setdefault("candidate_conflicts", [])
        conflicts.append({
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "conflicting_value": external_value,
            "source_evidence_id": source_evidence_id,
            "source_ref": source_ref,
        })
        self.backend.update(active_mem)
        return False, f"External conflict noted for key '{normalized_key}'; existing user memory preserved as authoritative.", active_mem

    def retrieve_memories(
        self,
        scope: Optional[MemoryScope] = None,
        scope_id: Optional[str] = None,
        key: Optional[str] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
    ) -> List[MemoryRecord]:
        """Retrieves memories from backend enforcing scope isolation."""
        return self.backend.list(
            scope=scope,
            scope_id=scope_id,
            key=key,
            status=status,
        )

    def retrieve_for_context(
        self,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
        query_keys: Optional[List[str]] = None,
    ) -> List[MemoryRecord]:
        """Hierarchical memory retrieval: PROJECT scope wins over USER scope."""
        retrieved: List[MemoryRecord] = []
        seen_keys: set = set()

        if project_scope_id:
            project_records = self.retrieve_memories(
                scope=MemoryScope.PROJECT,
                scope_id=project_scope_id,
                status=MemoryStatus.ACTIVE,
            )
            for rec in project_records:
                if not query_keys or rec.key in [k.lower() for k in query_keys]:
                    retrieved.append(rec)
                    seen_keys.add(rec.key)

        if user_scope_id:
            user_records = self.retrieve_memories(
                scope=MemoryScope.USER,
                scope_id=user_scope_id,
                status=MemoryStatus.ACTIVE,
            )
            for rec in user_records:
                if (not query_keys or rec.key in [k.lower() for k in query_keys]) and rec.key not in seen_keys:
                    retrieved.append(rec)
                    seen_keys.add(rec.key)

        return retrieved
