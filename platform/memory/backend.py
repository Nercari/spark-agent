"""SQLite and Filesystem Storage Backend for Declarative Memory Records."""

import os
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from platform.memory.contracts import (
    MemoryRecord,
    MemoryScope,
    MemoryKind,
    MemoryStatus,
)


class MemoryBackend(ABC):
    """Abstract interface defining the persistence contract for declarative memories."""

    @abstractmethod
    def get_memory(self, memory_id: str) -> Optional[MemoryRecord]:
        pass

    @abstractmethod
    def get_active_memory(self, scope: MemoryScope, scope_id: str, key: str) -> Optional[MemoryRecord]:
        pass

    @abstractmethod
    def retrieve_memories(
        self,
        scope: Optional[MemoryScope] = None,
        scope_id: Optional[str] = None,
        kind: Optional[MemoryKind] = None,
        status: Optional[MemoryStatus] = None,
        key: Optional[str] = None,
    ) -> List[MemoryRecord]:
        pass

    @abstractmethod
    def atomic_create_or_supersede(
        self,
        new_record: MemoryRecord,
        expected_active_revision: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[MemoryRecord]]:
        pass

    @abstractmethod
    def touch_memory_used(self, memory_id: str):
        pass

    @abstractmethod
    def update_metadata(self, memory_id: str, new_metadata: Dict[str, Any]):
        pass


class SqliteMemoryBackend(MemoryBackend):
    """SQLite implementation of MemoryBackend supporting multi-scope queries and atomic CAS updates."""

    _db_locks: Dict[str, threading.Lock] = {}
    _global_lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.expanduser("~/.spark/declarative_memory.sqlite3")
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._global_lock:
            if self.db_path not in self._db_locks:
                self._db_locks[self.db_path] = threading.Lock()
        self._lock = self._db_locks[self.db_path]
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memory_records (
                        id TEXT PRIMARY KEY,
                        scope TEXT NOT NULL,
                        scope_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        provenance_evidence_ids TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        last_confirmed_at TEXT NOT NULL,
                        last_used_at TEXT,
                        status TEXT NOT NULL,
                        supersedes_memory_id TEXT,
                        metadata TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_active_scope_key
                    ON memory_records (scope, scope_id, key)
                    WHERE status = 'ACTIVE'
                """)
                conn.commit()
            finally:
                conn.close()

    def get_memory(self, memory_id: str) -> Optional[MemoryRecord]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT * FROM memory_records WHERE id = ?", (memory_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_record(row)
            finally:
                conn.close()

    def get_active_memory(self, scope: MemoryScope, scope_id: str, key: str) -> Optional[MemoryRecord]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT * FROM memory_records
                    WHERE scope = ? AND scope_id = ? AND key = ? AND status = 'ACTIVE'
                """, (scope.value, scope_id, key))
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_record(row)
            finally:
                conn.close()

    def retrieve_memories(
        self,
        scope: Optional[MemoryScope] = None,
        scope_id: Optional[str] = None,
        kind: Optional[MemoryKind] = None,
        status: Optional[MemoryStatus] = None,
        key: Optional[str] = None,
    ) -> List[MemoryRecord]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                query = "SELECT * FROM memory_records WHERE 1=1"
                params: List[Any] = []
                if scope:
                    query += " AND scope = ?"
                    params.append(scope.value)
                if scope_id:
                    query += " AND scope_id = ?"
                    params.append(scope_id)
                if kind:
                    query += " AND kind = ?"
                    params.append(kind.value)
                if status:
                    query += " AND status = ?"
                    params.append(status.value)
                if key:
                    query += " AND key = ?"
                    params.append(key)

                query += " ORDER BY created_at DESC"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()
                return [self._row_to_record(r) for r in rows]
            finally:
                conn.close()

    def atomic_create_or_supersede(
        self,
        new_record: MemoryRecord,
        expected_active_revision: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[MemoryRecord]]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                conn.execute("BEGIN IMMEDIATE")

                cur.execute("""
                    SELECT * FROM memory_records
                    WHERE scope = ? AND scope_id = ? AND key = ? AND status = 'ACTIVE'
                """, (new_record.scope.value, new_record.scope_id, new_record.key))
                active_row = cur.fetchone()

                if active_row:
                    active_id = active_row["id"]
                    active_meta = json.loads(active_row["metadata"]) if active_row["metadata"] else {}
                    cur_rev = active_meta.get("revision", 1)

                    if expected_active_revision is not None and cur_rev != expected_active_revision:
                        conn.rollback()
                        return False, f"Stale write rejected: expected revision {expected_active_revision}, found {cur_rev}", None

                    # Mark old as superseded
                    cur.execute("""
                        UPDATE memory_records
                        SET status = 'SUPERSEDED'
                        WHERE id = ?
                    """, (active_id,))
                    new_record.supersedes_memory_id = active_id
                    new_record.metadata["revision"] = cur_rev + 1
                else:
                    new_record.metadata["revision"] = 1

                cur.execute("""
                    INSERT INTO memory_records (
                        id, scope, scope_id, kind, key, value, provenance_evidence_ids,
                        created_at, last_confirmed_at, last_used_at, status,
                        supersedes_memory_id, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_record.id,
                    new_record.scope.value,
                    new_record.scope_id,
                    new_record.kind.value,
                    new_record.key,
                    json.dumps(new_record.value) if not isinstance(new_record.value, str) else new_record.value,
                    json.dumps(new_record.provenance_evidence_ids),
                    new_record.created_at,
                    new_record.last_confirmed_at,
                    new_record.last_used_at,
                    new_record.status.value,
                    new_record.supersedes_memory_id,
                    json.dumps(new_record.metadata),
                ))

                conn.commit()
                return True, "Memory record created or superseded successfully", new_record
            except Exception as e:
                conn.rollback()
                return False, f"SQLite transaction failed: {str(e)}", None
            finally:
                conn.close()

    def touch_memory_used(self, memory_id: str):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                now_iso = datetime.now(timezone.utc).isoformat()
                cur.execute("SELECT metadata FROM memory_records WHERE id = ?", (memory_id,))
                row = cur.fetchone()
                if row:
                    meta = json.loads(row["metadata"]) if row["metadata"] else {}
                    meta["use_count"] = meta.get("use_count", 0) + 1
                    cur.execute("""
                        UPDATE memory_records
                        SET last_used_at = ?, metadata = ?
                        WHERE id = ?
                    """, (now_iso, json.dumps(meta), memory_id))
                    conn.commit()
            finally:
                conn.close()

    def update_metadata(self, memory_id: str, new_metadata: Dict[str, Any]):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE memory_records
                    SET metadata = ?
                    WHERE id = ?
                """, (json.dumps(new_metadata), memory_id))
                conn.commit()
            finally:
                conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        val_str = row["value"]
        try:
            val = json.loads(val_str)
        except Exception:
            val = val_str

        return MemoryRecord(
            id=row["id"],
            scope=MemoryScope(row["scope"]),
            scope_id=row["scope_id"],
            kind=MemoryKind(row["kind"]),
            key=row["key"],
            value=val,
            provenance_evidence_ids=json.loads(row["provenance_evidence_ids"]) if row["provenance_evidence_ids"] else [],
            created_at=row["created_at"],
            last_confirmed_at=row["last_confirmed_at"],
            last_used_at=row["last_used_at"],
            status=MemoryStatus(row["status"]),
            supersedes_memory_id=row["supersedes_memory_id"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )


# Alias for backwards compatibility
LocalFilesystemMemoryBackend = SqliteMemoryBackend
DurableSparkMemoryBackend = SqliteMemoryBackend
