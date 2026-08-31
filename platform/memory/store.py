"""Memory Store: Core Declarative Memory Lifecycle, Conflict Tracking, and CAS Interface."""

from typing import Any, Dict, List, Optional, Tuple
from platform.memory.contracts import (
    MemoryRecord,
    MemoryScope,
    MemoryKind,
    MemoryStatus,
)
from platform.memory.backend import LocalFilesystemMemoryBackend


class MemoryStore:
    """Manages declarative memory persistence, single-active-record invariant, and candidate conflicts."""

    def __init__(self, backend: Optional[LocalFilesystemMemoryBackend] = None):
        self.backend = backend or LocalFilesystemMemoryBackend()

    def get_memory(self, memory_id: str) -> Optional[MemoryRecord]:
        return self.backend.get_memory(memory_id)

    def retrieve_memories(
        self,
        scope: Optional[MemoryScope] = None,
        scope_id: Optional[str] = None,
        kind: Optional[MemoryKind] = None,
        status: Optional[MemoryStatus] = None,
        key: Optional[str] = None,
    ) -> List[MemoryRecord]:
        return self.backend.retrieve_memories(scope, scope_id, kind, status, key)

    def get_active_memory(self, scope: MemoryScope, scope_id: str, key: str) -> Optional[MemoryRecord]:
        return self.backend.get_active_memory(scope, scope_id, key)

    def touch_memory_used(self, memory_id: str):
        self.backend.touch_memory_used(memory_id)

    def create_or_update_memory(
        self,
        scope: MemoryScope,
        scope_id: str,
        kind: MemoryKind,
        key: str,
        value: str,
        confidence: float = 1.0,
        evidence_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expected_revision: Optional[int] = None,
        is_trusted_user_origin: bool = True,
    ) -> Tuple[bool, str, Optional[MemoryRecord]]:
        # Untrusted external claims cannot create or mutate standing active truth
        if not is_trusted_user_origin:
            active = self.get_active_memory(scope, scope_id, key)
            if active:
                # Ingest candidate conflict for revalidation tracking without mutating truth
                conflicts = active.metadata.get("candidate_conflicts", [])
                conflicts.append({
                    "untrusted_value": value,
                    "evidence_ids": evidence_ids or [],
                })
                active.metadata["candidate_conflicts"] = conflicts
                self.backend.update_metadata(active.id, active.metadata)
                return False, f"Untrusted candidate conflict recorded against active memory {key}.", active
            return False, f"Untrusted origin cannot create first memory for key {key}.", None

        import uuid
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        mem_id = f"mem_{uuid.uuid4().hex[:12]}"

        record = MemoryRecord(
            id=mem_id,
            scope=scope,
            scope_id=scope_id,
            kind=kind,
            key=key,
            value=value,
            status=MemoryStatus.ACTIVE,
            confidence=confidence,
            revision=1,
            created_at=now_iso,
            updated_at=now_iso,
            last_confirmed_at=now_iso,
            evidence_ids=evidence_ids or [],
            metadata=metadata or {},
        )

        return self.backend.atomic_create_or_supersede(
            new_record=record,
            expected_active_revision=expected_revision,
        )
