"""Declarative Memory SQLite Backend with Atomic Compare-and-Swap (CAS) Mutation."""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from platform.memory.contracts import MemoryRecord, MemoryScope, MemoryKind, MemoryStatus


class LocalFilesystemMemoryBackend:
    """Thread-safe SQLite storage for declarative memory records enforcing atomic CAS invariants."""

    _db_locks: Dict[str, threading.Lock] = {}
    _global_lock = threading.Lock()

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.expanduser("~/.spark/memory")
        self.db_path = os.path.join(self.base_dir, "declarative_memory.sqlite3")
        os.makedirs(self.base_dir, exist_ok=True)
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
                        status TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        revision INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_confirmed_at TEXT,
                        last_used_at TEXT,
                        use_count INTEGER NOT NULL DEFAULT 0,
                        evidence_ids TEXT NOT NULL,
                        metadata TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_active_unique_scope_key
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

                query += " ORDER BY updated_at DESC"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()
                return [self._row_to_record(r) for r in rows]
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

                if active_row is not None:
                    active_rev = active_row["revision"]
                    if expected_active_revision is not None and active_rev != expected_active_revision:
                        conn.rollback()
                        return False, f"Stale write rejected: expected revision {expected_active_revision}, found {active_rev}.", None

                    old_id = active_row["id"]
                    old_meta = json.loads(active_row["metadata"])
                    old_meta["superseded_by_id"] = new_record.id
                    now_iso = datetime.now(timezone.utc).isoformat()

                    cur.execute("""
                        UPDATE memory_records
                        SET status = 'SUPERSEDED', updated_at = ?, metadata = ?
                        WHERE id = ?
                    """, (now_iso, json.dumps(old_meta), old_id))

                    new_record.revision = active_rev + 1
                else:
                    if expected_active_revision is not None:
                        conn.rollback()
                        return False, f"Stale write rejected: expected revision {expected_active_revision}, but no active record exists.", None
                    new_record.revision = 1

                cur.execute("""
                    INSERT INTO memory_records (
                        id, scope, scope_id, kind, key, value, status, confidence,
                        revision, created_at, updated_at, last_confirmed_at, last_used_at,
                        use_count, evidence_ids, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_record.id,
                    new_record.scope.value,
                    new_record.scope_id,
                    new_record.kind.value,
                    new_record.key,
                    new_record.value,
                    new_record.status.value,
                    new_record.confidence,
                    new_record.revision,
                    new_record.created_at,
                    new_record.updated_at,
                    new_record.last_confirmed_at,
                    new_record.last_used_at,
                    new_record.use_count,
                    json.dumps(new_record.evidence_ids),
                    json.dumps(new_record.metadata),
                ))

                conn.commit()
                return True, f"Memory {new_record.key} successfully persisted with revision {new_record.revision}.", new_record
            except sqlite3.IntegrityError as e:
                conn.rollback()
                return False, f"Integrity constraint violation during memory CAS: {e}", None
            except Exception as e:
                conn.rollback()
                return False, f"Database error during memory CAS: {e}", None
            finally:
                conn.close()

    def touch_memory_used(self, memory_id: str):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                now_iso = datetime.now(timezone.utc).isoformat()
                cur.execute("""
                    UPDATE memory_records
                    SET use_count = use_count + 1, last_used_at = ?, updated_at = ?
                    WHERE id = ?
                """, (now_iso, now_iso, memory_id))
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
                    SET metadata = ?, updated_at = ?
                    WHERE id = ?
                """, (json.dumps(new_metadata), datetime.now(timezone.utc).isoformat(), memory_id))
                conn.commit()
            finally:
                conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"],
            scope=MemoryScope(row["scope"]),
            scope_id=row["scope_id"],
            kind=MemoryKind(row["kind"]),
            key=row["key"],
            value=row["value"],
            status=MemoryStatus(row["status"]),
            confidence=row["confidence"],
            revision=row["revision"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_confirmed_at=row["last_confirmed_at"] or "",
            last_used_at=row["last_used_at"],
            use_count=row["use_count"] or 0,
            evidence_ids=json.loads(row["evidence_ids"]) if row["evidence_ids"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
