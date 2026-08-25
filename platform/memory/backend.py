"""Durable SQLite-backed Storage Backend with Atomic CAS and Unique Active-Key Invariant."""

import abc
import os
import json
import uuid
import sqlite3
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

    @abc.abstractmethod
    def create_or_supersede_atomic(
        self,
        scope: MemoryScope,
        scope_id: str,
        kind: MemoryKind,
        key: str,
        value: Any,
        provenance_evidence_ids: List[str],
        expected_revision: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[MemoryRecord], Optional[MemoryRecord], bool, str]:
        """Atomically supersedes any existing active record and inserts new active record."""
        pass


class SqliteMemoryBackend(MemoryBackend):
    """SQLite-backed persistent memory backend providing genuine atomic CAS and unique active-key invariant."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_records (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_confirmed_at TEXT NOT NULL,
                    last_used_at TEXT,
                    status TEXT NOT NULL,
                    supersedes_memory_id TEXT,
                    revision TEXT NOT NULL,
                    metadata TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_active_scoped_key 
                ON memory_records(scope, scope_id, key) 
                WHERE status = 'ACTIVE';
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_scope_key 
                ON memory_records(scope, scope_id, key);
            """)
        finally:
            conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row[0],
            scope=MemoryScope(row[1]),
            scope_id=row[2],
            kind=MemoryKind(row[3]),
            key=row[4],
            value=json.loads(row[5]),
            provenance_evidence_ids=json.loads(row[6]),
            created_at=row[7],
            last_confirmed_at=row[8],
            last_used_at=row[9],
            status=MemoryStatus(row[10]),
            supersedes_memory_id=row[11],
            metadata=json.loads(row[13]),
        )

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, scope, scope_id, kind, key, value, provenance, created_at, last_confirmed_at, last_used_at, status, supersedes_memory_id, revision, metadata FROM memory_records WHERE id = ?", (record_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_record(row)
        finally:
            conn.close()

    def list(
        self,
        scope: Optional[MemoryScope] = None,
        scope_id: Optional[str] = None,
        key: Optional[str] = None,
        status: Optional[MemoryStatus] = None,
    ) -> List[MemoryRecord]:
        normalized_key = key.strip().lower().replace(" ", "_") if key else None
        query = "SELECT id, scope, scope_id, kind, key, value, provenance, created_at, last_confirmed_at, last_used_at, status, supersedes_memory_id, revision, metadata FROM memory_records WHERE 1=1"
        params: List[Any] = []

        if scope:
            query += " AND scope = ?"
            params.append(scope.value)
        if scope_id:
            query += " AND scope_id = ?"
            params.append(scope_id)
        if normalized_key:
            query += " AND key = ?"
            params.append(normalized_key)
        if status:
            query += " AND status = ?"
            params.append(status.value)

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [self._row_to_record(r) for r in rows]
        finally:
            conn.close()

    def put(self, record: MemoryRecord) -> None:
        rev = record.metadata.get("revision", f"rev_{uuid.uuid4().hex[:8]}")
        record.metadata["revision"] = rev
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO memory_records (
                    id, scope, scope_id, kind, key, value, provenance, created_at, last_confirmed_at, last_used_at, status, supersedes_memory_id, revision, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.id,
                record.scope.value,
                record.scope_id,
                record.kind.value,
                record.key,
                json.dumps(record.value),
                json.dumps(record.provenance_evidence_ids),
                record.created_at,
                record.last_confirmed_at,
                record.last_used_at,
                record.status.value,
                record.supersedes_memory_id,
                rev,
                json.dumps(record.metadata),
            ))
        finally:
            conn.close()

    def update(self, record: MemoryRecord, expected_revision: Optional[str] = None) -> Tuple[bool, str]:
        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.cursor()
            cur.execute("SELECT revision FROM memory_records WHERE id = ?", (record.id,))
            row = cur.fetchone()
            if not row:
                conn.execute("ROLLBACK;")
                return False, f"Memory record '{record.id}' not found."

            current_rev = row[0]
            if expected_revision and current_rev != expected_revision:
                conn.execute("ROLLBACK;")
                return False, f"Stale-write race detected on record '{record.id}': expected revision {expected_revision}, current is {current_rev}."

            new_rev = f"rev_{uuid.uuid4().hex[:8]}"
            record.metadata["revision"] = new_rev
            conn.execute("""
                UPDATE memory_records SET
                    status = ?,
                    value = ?,
                    last_confirmed_at = ?,
                    last_used_at = ?,
                    revision = ?,
                    metadata = ?
                WHERE id = ?
            """, (
                record.status.value,
                json.dumps(record.value),
                record.last_confirmed_at,
                record.last_used_at,
                new_rev,
                json.dumps(record.metadata),
                record.id,
            ))
            conn.execute("COMMIT;")
            return True, "Update succeeded."
        except Exception as e:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            return False, f"Update failed: {str(e)}"
        finally:
            conn.close()

    def create_or_supersede_atomic(
        self,
        scope: MemoryScope,
        scope_id: str,
        kind: MemoryKind,
        key: str,
        value: Any,
        provenance_evidence_ids: List[str],
        expected_revision: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[MemoryRecord], Optional[MemoryRecord], bool, str]:
        normalized_key = key.strip().lower().replace(" ", "_")
        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.cursor()
            cur.execute(
                "SELECT id, scope, scope_id, kind, key, value, provenance, created_at, last_confirmed_at, last_used_at, status, supersedes_memory_id, revision, metadata FROM memory_records WHERE scope = ? AND scope_id = ? AND key = ? AND status = 'ACTIVE'",
                (scope.value, scope_id, normalized_key),
            )
            row = cur.fetchone()

            superseded_rec: Optional[MemoryRecord] = None
            supersedes_id: Optional[str] = None

            if row:
                active_rec = self._row_to_record(row)
                current_rev = row[12]
                if expected_revision and current_rev != expected_revision:
                    conn.execute("ROLLBACK;")
                    return None, None, False, f"Stale-write race on key '{normalized_key}': expected revision {expected_revision}, got {current_rev}."

                superseded_rec = active_rec
                supersedes_id = active_rec.id
                superseded_rec.status = MemoryStatus.SUPERSEDED
                superseded_rec.metadata["superseded_at"] = datetime.now(timezone.utc).isoformat()
                
                conn.execute(
                    "UPDATE memory_records SET status = 'SUPERSEDED', metadata = ? WHERE id = ?",
                    (json.dumps(superseded_rec.metadata), superseded_rec.id),
                )

            now_iso = datetime.now(timezone.utc).isoformat()
            meta = metadata.copy() if metadata else {}
            new_rev = f"rev_{uuid.uuid4().hex[:8]}"
            meta["revision"] = new_rev

            new_rec = MemoryRecord(
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

            conn.execute("""
                INSERT INTO memory_records (
                    id, scope, scope_id, kind, key, value, provenance, created_at, last_confirmed_at, last_used_at, status, supersedes_memory_id, revision, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_rec.id,
                new_rec.scope.value,
                new_rec.scope_id,
                new_rec.kind.value,
                new_rec.key,
                json.dumps(new_rec.value),
                json.dumps(new_rec.provenance_evidence_ids),
                new_rec.created_at,
                new_rec.last_confirmed_at,
                new_rec.last_used_at,
                new_rec.status.value,
                new_rec.supersedes_memory_id,
                new_rev,
                json.dumps(new_rec.metadata),
            ))

            conn.execute("COMMIT;")
            return new_rec, superseded_rec, True, "Memory persisted successfully."
        except sqlite3.IntegrityError as ie:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            return None, None, False, f"Stale-write race detected (Active-key collision): {str(ie)}"
        except Exception as e:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            return None, None, False, f"Atomic memory transaction failed: {str(e)}"
        finally:
            conn.close()


class LocalFilesystemMemoryBackend(SqliteMemoryBackend):
    """Filesystem-backed memory backend with isolated SQLite database per directory."""

    def __init__(self, base_dir: str):
        db_path = os.path.join(base_dir, "memory.sqlite3")
        super().__init__(db_path=db_path)


class DurableSparkMemoryBackend(SqliteMemoryBackend):
    """Production memory backend configured with durable private runtime SQLite storage."""

    def __init__(self, persistent_storage_dir: Optional[str] = None):
        default_dir = os.path.expanduser("~/.spark/declarative_memory")
        base_dir = persistent_storage_dir or default_dir
        db_path = os.path.join(base_dir, "memory.sqlite3")
        super().__init__(db_path=db_path)
