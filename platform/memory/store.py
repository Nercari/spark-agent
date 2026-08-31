"""Declarative Memory Store managing atomic updates, conflict resolution, and record lifecycles."""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from platform.memory.contracts import MemoryRecord, MemoryScope, MemoryKind, MemoryStatus
from platform.memory.backend import MemoryBackend, DurableSparkMemoryBackend


class MemoryStore:
    """Service layer managing declarative memories with atomic CAS mutation, untrusted origin gating, and touch_used persistence."""

    def __init__(self, backend: Optional[MemoryBackend] = None):
        self.backend = backend or DurableSparkMemoryBackend()

    def get_memory(self, memory_id: str) -> Optional[MemoryRecord]:
        return self.backend.get_memory(memory_id)

    def get_active_memory(self, scope: MemoryScope, scope_id: str, key: str) -> Optional[MemoryRecord]:
        return self.backend.get_active_memory(scope, scope_id, key)

    def retrieve_memories(
        self,
        scope: Optional[MemoryScope] = None,
        scope_id: Optional[str] = None,
        kind: Optional[MemoryKind] = None,
        status: Optional[MemoryStatus] = None,
        key: Optional[str] = None,
    ) -> List[MemoryRecord]:
        return self.backend.retrieve_memories(scope, scope_id, kind, status, key)

    def create_or_update_memory(
        self,
        scope: MemoryScope,
        scope_id: str,
        kind: MemoryKind,
        key: str,
        value: Any,
        evidence_ids: Optional[List[str]] = None,
        is_trusted_user_origin: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        expected_active_revision: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[MemoryRecord]]:
        active_rec = self.backend.get_active_memory(scope, scope_id, key)

        if not is_trusted_user_origin:
            if active_rec is None:
                return False, f"Untrusted origin cannot create new standing memory `{key}`.", None

            # Untrusted origin contradicting existing active memory -> log conflict
            cur_meta = dict(active_rec.metadata)
            conflicts = cur_meta.get("candidate_conflicts", [])
            conflicts.append({
                "proposed_value": value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trusted": False,
            })
            cur_meta["candidate_conflicts"] = conflicts
            self.backend.update_metadata(active_rec.id, cur_meta)
            return False, f"Untrusted candidate contradiction logged for `{key}` without mutating value.", active_rec

        now_iso = datetime.now(timezone.utc).isoformat()
        new_rec = MemoryRecord(
            id=f"mem_{uuid.uuid4().hex[:12]}",
            scope=scope,
            scope_id=scope_id,
            kind=kind,
            key=key,
            value=value,
            provenance_evidence_ids=evidence_ids or [],
            created_at=active_rec.created_at if active_rec else now_iso,
            last_confirmed_at=now_iso,
            status=MemoryStatus.ACTIVE,
            metadata=metadata or {},
        )

        expected_rev = active_rec.metadata.get("revision", 1) if active_rec else None
        if expected_active_revision is not None:
            expected_rev = expected_active_revision

        return self.backend.atomic_create_or_supersede(new_rec, expected_active_revision=expected_rev)

    def touch_memory_used(self, memory_id: str):
        self.backend.touch_memory_used(memory_id)

    def mark_memory_stale(self, memory_id: str) -> bool:
        rec = self.backend.get_memory(memory_id)
        if not rec:
            return False
        meta = dict(rec.metadata)
        meta["revalidation_needed"] = True
        self.backend.update_metadata(memory_id, meta)
        return True
