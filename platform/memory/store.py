"""Durable Declarative Memory Store with Scope Isolation, Versioning, and Conflict Protection."""

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


class MemoryStore:
    """Manages persistent declarative memories across USER and PROJECT scopes."""

    def __init__(self, base_storage_dir: Optional[str] = None):
        self.base_dir = base_storage_dir or "/working_dir/c_b490a8c7dd21c813/.learning/memory"
        os.makedirs(self.base_dir, exist_ok=True)
        self.records_dir = os.path.join(self.base_dir, "records")
        os.makedirs(self.records_dir, exist_ok=True)

    def _get_record_path(self, record_id: str) -> str:
        return os.path.join(self.records_dir, f"{record_id}.json")

    def _save_record(self, record: MemoryRecord):
        with open(self._get_record_path(record.id), "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)

    def get_memory(self, record_id: str) -> Optional[MemoryRecord]:
        path = self._get_record_path(record_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return MemoryRecord.from_dict(json.load(f))

    def create_or_update_memory(
        self,
        scope: MemoryScope,
        scope_id: str,
        kind: MemoryKind,
        key: str,
        value: Any,
        provenance_evidence_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[MemoryRecord, Optional[MemoryRecord]]:
        """Creates a memory or supersedes an existing active memory with a newer trusted value."""
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
            superseded_record = existing_records[0]
            supersedes_id = superseded_record.id
            superseded_record.status = MemoryStatus.SUPERSEDED
            superseded_record.metadata["superseded_at"] = datetime.now(timezone.utc).isoformat()
            self._save_record(superseded_record)

        now_iso = datetime.now(timezone.utc).isoformat()
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
            metadata=metadata or {},
        )
        self._save_record(new_record)
        return new_record, superseded_record

    def handle_external_conflict(
        self,
        scope: MemoryScope,
        scope_id: str,
        key: str,
        external_value: Any,
        source_evidence_id: str,
        source_ref: str = "",
    ) -> Tuple[bool, str, Optional[MemoryRecord]]:
        """Handles conflicting external evidence without destructively overwriting user-authorized memory."""
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
        self._save_record(active_mem)
        return False, f"External conflict noted for key '{normalized_key}'; existing user memory preserved as authoritative.", active_mem

    def retrieve_memories(
        self,
        scope: Optional[MemoryScope] = None,
        scope_id: Optional[str] = None,
        key: Optional[str] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
    ) -> List[MemoryRecord]:
        """Retrieves memories enforcing scope isolation."""
        normalized_key = key.strip().lower().replace(" ", "_") if key else None
        results = []

        if not os.path.exists(self.records_dir):
            return results

        for fname in os.listdir(self.records_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.records_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            rec = MemoryRecord.from_dict(data)

            if status and rec.status != status:
                continue
            if scope and rec.scope != scope:
                continue
            if scope_id and rec.scope_id != scope_id:
                continue
            if normalized_key and rec.key != normalized_key:
                continue

            results.append(rec)

        return results

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
