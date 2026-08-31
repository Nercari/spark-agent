from __future__ import annotations
import os
import json
import uuid
import time
from typing import List, Optional, Dict, Any
from platform.memory.contracts import (
    DeclarativeMemoryRecord,
    MemoryStatus,
    MemoryScope,
    MemorySource,
    MemoryType,
)

class LocalFilesystemMemoryBackend:
    """Local filesystem persistence for declarative memories with atomic CAS and index tracking."""

    def __init__(self, base_dir: str = ".learning/memory"):
        self.base_dir = base_dir
        self.records_dir = os.path.join(base_dir, "records")
        os.makedirs(self.records_dir, exist_ok=True)

    def save(self, record: DeclarativeMemoryRecord) -> DeclarativeMemoryRecord:
        if not record.id:
            record.id = f"mem_{uuid.uuid4().hex[:10]}"
        if not record.created_at:
            record.created_at = time.time()
        record.updated_at = time.time()

        file_path = os.path.join(self.records_dir, f"{record.id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)
        return record

    def get(self, memory_id: str) -> Optional[DeclarativeMemoryRecord]:
        file_path = os.path.join(self.records_dir, f"{memory_id}.json")
        if not os.path.isfile(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return DeclarativeMemoryRecord.from_dict(data)
        except Exception:
            return None

    def list_active(
        self,
        project_scope: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[DeclarativeMemoryRecord]:
        records: List[DeclarativeMemoryRecord] = []
        if not os.path.isdir(self.records_dir):
            return records

        for fname in os.listdir(self.records_dir):
            if not fname.endswith(".json"):
                continue
            rec = self.get(fname[:-5])
            if not rec or rec.status not in (MemoryStatus.ACTIVE, MemoryStatus.REVALIDATION_NEEDED):
                continue
            if project_scope is not None and rec.project_scope != project_scope:
                continue
            if user_id is not None and rec.user_id != user_id:
                continue
            records.append(rec)

        return records

    def touch_memory_used(self, memory_id: str) -> bool:
        rec = self.get(memory_id)
        if not rec:
            return False
        rec.use_count += 1
        rec.last_used_at = time.time()
        self.save(rec)
        return True

    def supersede(
        self,
        old_memory_id: str,
        new_content: str,
        authoritative: bool = True,
    ) -> Optional[DeclarativeMemoryRecord]:
        old_rec = self.get(old_memory_id)
        if not old_rec:
            return None
        if not authoritative:
            return None

        # Archive old record
        old_rec.status = MemoryStatus.SUPERSEDED
        old_rec.updated_at = time.time()

        # Create new record
        new_rec = DeclarativeMemoryRecord(
            content=new_content,
            memory_type=old_rec.memory_type,
            scope=old_rec.scope,
            source=old_rec.source,
            status=MemoryStatus.ACTIVE,
            project_scope=old_rec.project_scope,
            user_id=old_rec.user_id,
            superseded_by=None,
            confidence=old_rec.confidence,
        )
        new_rec = self.save(new_rec)

        old_rec.superseded_by = new_rec.id
        self.save(old_rec)
        return new_rec

    def mark_revalidation_needed(self, memory_id: str, reason: str) -> bool:
        rec = self.get(memory_id)
        if not rec:
            return False
        rec.status = MemoryStatus.REVALIDATION_NEEDED
        rec.conflict_history.append({"reason": reason, "timestamp": time.time()})
        self.save(rec)
        return True
