"""Telemetry and Outcome Ledger for Measurable Learning Improvement."""

import os
import json
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
    """Records and aggregates operational telemetry for learned Skills and Memories."""

    def __init__(self, ledger_path: Optional[str] = None):
        default_path = os.path.expanduser("~/.spark/curator/telemetry.jsonl")
        self.ledger_path = ledger_path or default_path
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)

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
            used_str = str(used).upper()
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
        self._append_record(rec)
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
            used_str = str(used).upper()
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
        self._append_record(rec)
        return rec

    def _append_record(self, record: LearningOutcomeRecord):
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

    def get_all_records(self) -> List[LearningOutcomeRecord]:
        if not os.path.exists(self.ledger_path):
            return []
        records = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(LearningOutcomeRecord.from_dict(json.loads(line)))
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
                if r.metadata.get("conflict_observed", False):
                    telemetry.conflict_count += 1
                if r.metadata.get("is_correction", False):
                    telemetry.correction_count += 1

        return telemetry
