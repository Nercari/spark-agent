"""Curator Telemetry: SQLite Atomic Persistence for Usage, Outcomes, and Rollbacks."""

import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from platform.learning.contracts import VerificationStatus
from platform.curator.contracts import (
    ArtifactType,
    ObservedEffect,
    UsageState,
    SkillTelemetry,
    MemoryTelemetry,
    CuratorActionRecord,
    CuratorDecision,
)
from platform.memory.contracts import MemoryScope


class LearningTelemetryLedger:
    """Thread-safe SQLite storage recording task-level learning events and aggregated telemetry."""

    _db_locks: Dict[str, threading.Lock] = {}
    _global_lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.expanduser("~/.spark/telemetry.sqlite3")
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
                    CREATE TABLE IF NOT EXISTS learning_outcomes (
                        artifact_type TEXT NOT NULL,
                        artifact_id TEXT NOT NULL,
                        version_or_record_id TEXT NOT NULL,
                        task_run_id TEXT NOT NULL,
                        retrieved INTEGER NOT NULL,
                        used TEXT NOT NULL,
                        task_family TEXT NOT NULL,
                        verification_status TEXT NOT NULL,
                        recovery_required INTEGER NOT NULL,
                        observed_effect TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        PRIMARY KEY (artifact_type, artifact_id, version_or_record_id, task_run_id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS curator_actions (
                        action_id TEXT PRIMARY KEY,
                        task_run_id TEXT NOT NULL,
                        artifact_id TEXT NOT NULL,
                        evaluated_version TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        execution_status TEXT NOT NULL,
                        runtime_before_hash TEXT,
                        runtime_after_hash TEXT,
                        rollback_target TEXT,
                        timestamp TEXT NOT NULL,
                        details TEXT,
                        audit_trail TEXT
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    def record_skill_outcome(
        self,
        skill_name: str,
        skill_version: str,
        task_run_id: str,
        retrieved: bool,
        used: UsageState,
        task_family: str = "default_task_family",
        verification_status: VerificationStatus = VerificationStatus.UNKNOWN,
        recovery_required: bool = False,
        observed_effect: ObservedEffect = ObservedEffect.UNKNOWN,
    ):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                now_iso = datetime.now(timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO learning_outcomes (
                        artifact_type, artifact_id, version_or_record_id, task_run_id,
                        retrieved, used, task_family, verification_status, recovery_required,
                        observed_effect, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(artifact_type, artifact_id, version_or_record_id, task_run_id)
                    DO UPDATE SET
                        retrieved = excluded.retrieved,
                        used = excluded.used,
                        task_family = excluded.task_family,
                        verification_status = excluded.verification_status,
                        recovery_required = excluded.recovery_required,
                        observed_effect = excluded.observed_effect,
                        timestamp = excluded.timestamp
                """, (
                    ArtifactType.SKILL.value,
                    skill_name,
                    skill_version,
                    task_run_id,
                    1 if retrieved else 0,
                    used.value if isinstance(used, UsageState) else str(used),
                    task_family,
                    verification_status.value,
                    1 if recovery_required else 0,
                    observed_effect.value,
                    now_iso,
                ))
                conn.commit()
            finally:
                conn.close()

    def record_memory_outcome(
        self,
        memory_id: str,
        task_run_id: str,
        retrieved: bool,
        used: UsageState,
        task_family: str = "default_task_family",
        verification_status: VerificationStatus = VerificationStatus.UNKNOWN,
        observed_effect: ObservedEffect = ObservedEffect.UNKNOWN,
    ):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                now_iso = datetime.now(timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO learning_outcomes (
                        artifact_type, artifact_id, version_or_record_id, task_run_id,
                        retrieved, used, task_family, verification_status, recovery_required,
                        observed_effect, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(artifact_type, artifact_id, version_or_record_id, task_run_id)
                    DO UPDATE SET
                        retrieved = excluded.retrieved,
                        used = excluded.used,
                        task_family = excluded.task_family,
                        verification_status = excluded.verification_status,
                        recovery_required = excluded.recovery_required,
                        observed_effect = excluded.observed_effect,
                        timestamp = excluded.timestamp
                """, (
                    ArtifactType.MEMORY.value,
                    memory_id,
                    memory_id,
                    task_run_id,
                    1 if retrieved else 0,
                    used.value if isinstance(used, UsageState) else str(used),
                    task_family,
                    verification_status.value,
                    0,
                    observed_effect.value,
                    now_iso,
                ))
                conn.commit()
            finally:
                conn.close()

    def get_skill_telemetry(
        self,
        skill_name: str,
        skill_version: str,
        task_family: Optional[str] = None,
    ) -> SkillTelemetry:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                query = """
                    SELECT
                        COUNT(CASE WHEN retrieved = 1 THEN 1 END) as retrieval_count,
                        COUNT(CASE WHEN used = 'TRUE' THEN 1 END) as use_count,
                        COUNT(CASE WHEN used = 'UNKNOWN' THEN 1 END) as unknown_use_count,
                        COUNT(CASE WHEN used = 'FALSE' THEN 1 END) as unused_count,
                        COUNT(CASE WHEN verification_status = 'VERIFIED_SUCCESS' AND used = 'TRUE' THEN 1 END) as verified_success_count,
                        COUNT(CASE WHEN verification_status = 'VERIFIED_FAILURE' AND used = 'TRUE' THEN 1 END) as verified_failure_count,
                        COUNT(CASE WHEN recovery_required = 1 AND used = 'TRUE' THEN 1 END) as recovery_required_count,
                        MAX(timestamp) as last_used_at
                    FROM learning_outcomes
                    WHERE artifact_type = ? AND artifact_id = ? AND version_or_record_id = ?
                """
                params: List[Any] = [ArtifactType.SKILL.value, skill_name, skill_version]
                if task_family:
                    query += " AND task_family = ?"
                    params.append(task_family)

                cur.execute(query, tuple(params))
                row = cur.fetchone()

                retrievals = row["retrieval_count"] or 0
                uses = row["use_count"] or 0
                unknown_uses = row["unknown_use_count"] or 0
                unused = row["unused_count"] or 0
                successes = row["verified_success_count"] or 0
                failures = row["verified_failure_count"] or 0
                recoveries = row["recovery_required_count"] or 0
                last_used = row["last_used_at"]

                return SkillTelemetry(
                    skill_name=skill_name,
                    skill_version=skill_version,
                    task_family=task_family or "all",
                    retrieval_count=retrievals,
                    use_count=uses,
                    unknown_use_count=unknown_uses,
                    unused_count=unused,
                    verified_success_count=successes,
                    verified_failure_count=failures,
                    recovery_required_count=recoveries,
                    last_used_at=last_used,
                )
            finally:
                conn.close()

    def get_memory_telemetry(self, memory_id: str) -> MemoryTelemetry:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT
                        COUNT(CASE WHEN retrieved = 1 THEN 1 END) as retrieval_count,
                        COUNT(CASE WHEN used = 'TRUE' THEN 1 END) as use_count,
                        COUNT(CASE WHEN used = 'UNKNOWN' THEN 1 END) as unknown_use_count,
                        COUNT(CASE WHEN used = 'FALSE' THEN 1 END) as unused_count,
                        COUNT(CASE WHEN verification_status = 'VERIFIED_SUCCESS' AND used = 'TRUE' THEN 1 END) as verified_success_count,
                        MAX(timestamp) as last_used_at
                    FROM learning_outcomes
                    WHERE artifact_type = ? AND artifact_id = ?
                """, (ArtifactType.MEMORY.value, memory_id))
                row = cur.fetchone()

                return MemoryTelemetry(
                    memory_id=memory_id,
                    scope=MemoryScope.PROJECT,
                    scope_id="default",
                    key=memory_id,
                    retrieval_count=row["retrieval_count"] or 0,
                    use_count=row["use_count"] or 0,
                    unknown_use_count=row["unknown_use_count"] or 0,
                    unused_count=row["unused_count"] or 0,
                    verified_success_count=row["verified_success_count"] or 0,
                    last_used_at=row["last_used_at"],
                )
            finally:
                conn.close()
