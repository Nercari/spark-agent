"""Durable Storage Backend Abstraction with Lightweight Revision (CAS) Protection."""

import abc
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


class MemoryBackend(abc.ABC):
    """Abstract interface for storing and retrieving declarative memory records."""

    @abc.abstractmethod
    def get(self, record_id: str) -> Optional[MemoryRecord]:
        pass

    @abc.abstractmethod
    def list(
        self,
        scope: Optional[MemoryScope] = None,
        scope_id: Optional[str] = None,
        key: Optional[str] = None,
        status: Optional[MemoryStatus] = None,
    ) -> List[MemoryRecord]:
        pass

    @abc.abstractmethod
    def put(self, record: MemoryRecord) -> None:
        pass

    @abc.abstractmethod
    def update(self, record: MemoryRecord, expected_revision: Optional[str] = None) -> Tuple[bool, str]:
        pass


class LocalFilesystemMemoryBackend(MemoryBackend):
    """Filesystem-backed memory backend with revision tracking."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.records_dir = os.path.join(self.base_dir, "records")
        os.makedirs(self.records_dir, exist_ok=True)

    def _get_path(self, record_id: str) -> str:
        return os.path.join(self.records_dir, f"{record_id}.json")

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        path = self._get_path(record_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return MemoryRecord.from_dict(json.load(f))

    def list(
        self,
        scope: Optional[MemoryScope] = None,
        scope_id: Optional[str] = None,
        key: Optional[str] = None,
        status: Optional[MemoryStatus] = None,
    ) -> List[MemoryRecord]:
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

    def put(self, record: MemoryRecord) -> None:
        if "revision" not in record.metadata:
            record.metadata["revision"] = f"rev_{uuid.uuid4().hex[:8]}"
        with open(self._get_path(record.id), "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)

    def update(self, record: MemoryRecord, expected_revision: Optional[str] = None) -> Tuple[bool, str]:
        """Lightweight Compare-And-Swap (CAS) update."""
        existing = self.get(record.id)
        if not existing:
            return False, f"Memory record '{record.id}' not found."

        current_rev = existing.metadata.get("revision")
        if expected_revision and current_rev != expected_revision:
            return (
                False,
                f"Stale-write race detected on record '{record.id}': expected revision {expected_revision}, current is {current_rev}.",
            )

        record.metadata["revision"] = f"rev_{uuid.uuid4().hex[:8]}"
        with open(self._get_path(record.id), "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)
        return True, "Update succeeded."


class DurableSparkMemoryBackend(LocalFilesystemMemoryBackend):
    """Production memory backend configured with durable private runtime storage."""

    def __init__(self, persistent_storage_dir: Optional[str] = None):
        default_dir = os.path.expanduser("~/.spark/declarative_memory")
        base_dir = persistent_storage_dir or default_dir
        super().__init__(base_dir=base_dir)
