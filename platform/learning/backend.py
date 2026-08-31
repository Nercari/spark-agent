"""SQLite Storage Backend for Skill Versions, TaskRuns, and Reflection Logs."""

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional
from platform.learning.contracts import SkillVersion, TaskRun, LearningMutation


class SQLiteLearningBackend:
    """Thread-safe SQLite storage for versioned procedural skills and immutable execution logs."""

    _db_locks: Dict[str, threading.Lock] = {}
    _global_lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.expanduser("~/.spark/learning.sqlite3")
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
                    CREATE TABLE IF NOT EXISTS skill_versions (
                        skill_name TEXT NOT NULL,
                        version_id TEXT NOT NULL,
                        parent_version_id TEXT,
                        content TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        created_from_task_run_id TEXT,
                        change_reason TEXT,
                        diff TEXT,
                        status TEXT NOT NULL,
                        PRIMARY KEY (skill_name, version_id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS task_runs (
                        id TEXT PRIMARY KEY,
                        goal TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        completed_at TEXT NOT NULL,
                        user_scope_id TEXT NOT NULL,
                        project_scope_id TEXT NOT NULL,
                        skill_name TEXT NOT NULL,
                        skill_version TEXT NOT NULL,
                        evidence_events TEXT NOT NULL,
                        final_output TEXT,
                        verification_status TEXT NOT NULL,
                        verification_details TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS learning_mutations (
                        id TEXT PRIMARY KEY,
                        task_run_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        target_skill TEXT NOT NULL,
                        base_version_id TEXT NOT NULL,
                        base_version_hash TEXT NOT NULL,
                        proposed_content TEXT NOT NULL,
                        diff TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        evidence_ids TEXT NOT NULL,
                        recovery_verified INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        committed_at TEXT
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    def save_version(self, version: SkillVersion):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO skill_versions (
                        skill_name, version_id, parent_version_id, content, content_hash,
                        created_at, created_from_task_run_id, change_reason, diff, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    version.skill_name,
                    version.version_id,
                    version.parent_version_id,
                    version.content,
                    version.content_hash,
                    version.created_at,
                    version.created_from_task_run_id,
                    version.change_reason,
                    version.diff,
                    version.status,
                ))
                conn.commit()
            finally:
                conn.close()

    def get_version(self, skill_name: str, version_id: str) -> Optional[SkillVersion]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT * FROM skill_versions WHERE skill_name = ? AND version_id = ?
                """, (skill_name, version_id))
                row = cur.fetchone()
                if not row:
                    return None
                return SkillVersion(
                    version_id=row["version_id"],
                    skill_name=row["skill_name"],
                    parent_version_id=row["parent_version_id"],
                    content=row["content"],
                    content_hash=row["content_hash"],
                    created_at=row["created_at"],
                    created_from_task_run_id=row["created_from_task_run_id"],
                    change_reason=row["change_reason"],
                    diff=row["diff"],
                    status=row["status"],
                )
            finally:
                conn.close()

    def save_task_run(self, task_run: TaskRun):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO task_runs (
                        id, goal, started_at, completed_at, user_scope_id, project_scope_id,
                        skill_name, skill_version, evidence_events, final_output,
                        verification_status, verification_details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_run.id,
                    task_run.goal,
                    task_run.started_at,
                    task_run.completed_at,
                    task_run.user_scope_id,
                    task_run.project_scope_id,
                    task_run.skill_name,
                    task_run.skill_version,
                    json.dumps([e.to_dict() for e in task_run.evidence_events]),
                    task_run.final_output,
                    task_run.verification_status.value if hasattr(task_run.verification_status, "value") else str(task_run.verification_status),
                    json.dumps(task_run.verification_details),
                ))
                conn.commit()
            finally:
                conn.close()
