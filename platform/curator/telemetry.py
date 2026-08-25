"""Telemetry and Outcome Ledger for Measurable Learning Improvement (SQLite Persistence & Concurrency Safe)."""

import os
import json
import sqlite3
from typing import Any, Dict, List, Optional
from platform.learning.contracts import VerificationStatus
from platform.memory.contracts import MemoryScope
from platform.curator.contracts import (
    ArtifactType,
    ObservedEffect,
    UsageState,
    LearningOutcomeRecord,
    SkillTelemetry,
    MemoryTelemetry,
)


class LearningTelemetryLedger:
    """Records and aggregates operational telemetry for learned Skills and Memories with SQLite concurrency safety."""

    def __init__(self, db_path: Optional[str] = None, ledger_path: Optional[str] = None):
        target = db_path or ledger_path
        if target:
            if target.endswith(".jsonl"):
                self.db_path = target[:-6] + ".sqlite3"
            else:
                self.db_path = target
        else:
            self.db_path = os.path.expanduser("~/.spark/curator/telemetry.sqlite3")

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
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
                    metadata TEXT NOT NULL,
                    PRIMARY KEY (artifact_type, artifact_id, task_run_id)
                );
                """
            )
            conn.commit()

    def record_skill_outcome(
        self,
        skill_name: str,
        skill_version: str,
        task_run_id: str,
        retrieved: bool,
        used: Any,
        verification_status: VerificationStatus,
        task_family: str = "default_task_family",
        recovery_required: bool = False,
        observed_effect: ObservedEffect = ObservedEffect.UNKNOWN,
    ) -> LearningOutcomeRecord:
        if isinstance(used, bool):
            used_str = "TRUE" if used else "FALSE"
        elif isinstance(used, UsageState):
            used_str = used.value
        else:
            used_str = str(used).upper() if used is not None else "UNKNOWN"
            if used_str not in {"TRUE", "FALSE", "UNKNOWN"}:
                used_str = "UNKNOWN"

        rec = LearningOutcomeRecord(
            artifact_type=ArtifactType.SKILL,
            artifact_id=skill_name,
            version_or_record_id=skill_version,
            task_run_id=task_run_id,
            retrieved=retrieved,
            used=used_str,
            task_family=task_family,
            verification_status=verification_status,
            recovery_required=recovery_required,
            observed_effect=observed_effect,
        )
        self._save_record(rec)
        return rec

    def record_memory_outcome(
        self,
        memory_id: str,
        task_run_id: str,
        retrieved: bool,
        used: Any,
        verification_status: VerificationStatus,
        observed_effect: ObservedEffect = ObservedEffect.UNKNOWN,
        metadata: Optional[Dict] = None,
    ) -> LearningOutcomeRecord:
        if isinstance(used, bool):
            used_str = "TRUE" if used else "FALSE"
        elif isinstance(used, UsageState):
            used_str = used.value
        else:
            used_str = str(used).upper() if used is not None else "UNKNOWN"
            if used_str not in {"TRUE", "FALSE", "UNKNOWN"}:
                used_str = "UNKNOWN"

        rec = LearningOutcomeRecord(
            artifact_type=ArtifactType.MEMORY,
            artifact_id=memory_id,
            version_or_record_id=memory_id,
            task_run_id=task_run_id,
            retrieved=retrieved,
            used=used_str,
            verification_status=verification_status,
            observed_effect=observed_effect,
            metadata=metadata or {},
        )
        self._save_record(rec)
        return rec

    def _save_record(self, record: LearningOutcomeRecord):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO learning_outcomes (
                    artifact_type, artifact_id, version_or_record_id, task_run_id,
                    retrieved, used, task_family, verification_status, recovery_required,
                    observed_effect, timestamp, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_type, artifact_id, task_run_id) DO UPDATE SET
                    version_or_record_id=excluded.version_or_record_id,
                    retrieved=excluded.retrieved,
                    used=excluded.used,
                    task_family=excluded.task_family,
                    verification_status=excluded.verification_status,
                    recovery_required=excluded.recovery_required,
                    observed_effect=excluded.observed_effect,
                    timestamp=excluded.timestamp,
                    metadata=excluded.metadata;
                """,
                (
                    record.artifact_type.value,
                    record.artifact_id,
                    record.version_or_record_id,
                    record.task_run_id,
                    1 if record.retrieved else 0,
                    record.used,
                    record.task_family,
                    record.verification_status.value,
                    1 if record.recovery_required else 0,
                    record.observed_effect.value,
                    record.timestamp,
                    json.dumps(record.metadata),
                ),
            )
            conn.commit()

    def get_all_records(self) -> List[LearningOutcomeRecord]:
        records = []
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM learning_outcomes ORDER BY timestamp ASC;")
            for row in cur.fetchall():
                records.append(
                    LearningOutcomeRecord(
                        artifact_type=ArtifactType(row["artifact_type"]),
                        artifact_id=row["artifact_id"],
                        version_or_record_id=row["version_or_record_id"],
                        task_run_id=row["task_run_id"],
                        retrieved=bool(row["retrieved"]),
                        used=row["used"],
                        task_family=row["task_family"],
                        verification_status=VerificationStatus(row["verification_status"]),
                        recovery_required=bool(row["recovery_required"]),
                        observed_effect=ObservedEffect(row["observed_effect"]),
                        timestamp=row["timestamp"],
                        metadata=json.loads(row["metadata"]),
                    )
                )
        return records

    def get_skill_telemetry(self, skill_name: str, skill_version: str, task_family: Optional[str] = None) -> SkillTelemetry:
        records = self.get_all_records()
        telemetry = SkillTelemetry(skill_name=skill_name, skill_version=skill_version, task_family=task_family or "all")

        for r in records:
            if r.artifact_type == ArtifactType.SKILL and r.artifact_id == skill_name and r.version_or_record_id == skill_version:
                if task_family and r.task_family != task_family:
                    continue
                if r.retrieved:
                    telemetry.retrieval_count += 1
                if r.used == "TRUE":
                    telemetry.use_count += 1
                    telemetry.last_used_at = r.timestamp
                elif r.used == "UNKNOWN":
                    telemetry.unknown_use_count += 1

                if r.verification_status == VerificationStatus.VERIFIED_SUCCESS:
                    telemetry.verified_success_count += 1
                elif r.verification_status == VerificationStatus.VERIFIED_FAILURE:
                    telemetry.verified_failure_count += 1
                if r.recovery_required:
                    telemetry.recovery_required_count += 1

        return telemetry

    def get_memory_telemetry(self, memory_id: str, scope: MemoryScope = MemoryScope.PROJECT, scope_id: str = "", key: str = "") -> MemoryTelemetry:
        records = self.get_all_records()
        telemetry = MemoryTelemetry(memory_id=memory_id, scope=scope, scope_id=scope_id, key=key)

        for r in records:
            if r.artifact_type == ArtifactType.MEMORY and r.artifact_id == memory_id:
                if r.retrieved:
                    telemetry.retrieval_count += 1
                if r.used == "TRUE":
                    telemetry.use_count += 1
                    telemetry.last_used_at = r.timestamp
                elif r.used == "UNKNOWN":
                    telemetry.unknown_use_count += 1

                if r.verification_status == VerificationStatus.VERIFIED_SUCCESS:
                    telemetry.verified_success_count += 1
                if r.metadata.get("conflict_observed", False) or r.metadata.get("candidate_conflicts"):
                    telemetry.conflict_count += len(r.metadata.get("candidate_conflicts", [1]))
                if r.metadata.get("is_correction", False):
                    telemetry.correction_count += 1

        return telemetry
