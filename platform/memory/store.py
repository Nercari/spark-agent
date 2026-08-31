from __future__ import annotations
import os
import json
import uuid
import time
from typing import List, Optional, Dict
from platform.memory.contracts import (
    DeclarativeMemoryRecord,
    MemoryStatus,
    MemoryScope,
    MemorySource,
)
from platform.memory.backend import LocalFilesystemMemoryBackend

class MemoryStore:
    """Store managing declarative memory records with atomic CAS, supersession,
    and staleness/utility touch tracking."""

    def __init__(self, backend: Optional[LocalFilesystemMemoryBackend] = None):
        self.backend = backend or LocalFilesystemMemoryBackend()

    def save(self, record: DeclarativeMemoryRecord) -> DeclarativeMemoryRecord:
        """Save a new declarative record."""
        return self.backend.save(record)

    def get(self, memory_id: str) -> Optional[DeclarativeMemoryRecord]:
        """Get record by ID."""
        return self.backend.get(memory_id)

    def list_active(
        self,
        project_scope: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[DeclarativeMemoryRecord]:
        """List active memories filtered by project or user scope."""
        return self.backend.list_active(project_scope=project_scope, user_id=user_id)

    def touch_memory_used(self, memory_id: str) -> bool:
        """EXP-05: Record usage of memory to update utility metrics and last_used_at."""
        return self.backend.touch_memory_used(memory_id)

    def supersede(
        self,
        old_memory_id: str,
        new_content: str,
        authoritative: bool = True,
    ) -> Optional[DeclarativeMemoryRecord]:
        """Supersede an existing memory record atomically using CAS."""
        return self.backend.supersede(
            old_memory_id=old_memory_id,
            new_content=new_content,
            authoritative=authoritative,
        )

    def mark_revalidation_needed(self, memory_id: str, reason: str) -> bool:
        """Mark a record as needing revalidation due to contradiction."""
        return self.backend.mark_revalidation_needed(memory_id, reason)
