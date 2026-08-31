"""Skill Backend & Runtime Bridge Interface with TaskRun Provenance & Stale-Write Protection."""

import abc
import os
import json
import difflib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
from platform.learning.contracts import SkillVersion, LearningMutation, generate_sha256
from platform.learning.version_store import SkillVersionStore


@dataclass
class SparkSkillUpdateManifest:
    """Represents a payload prepared for dispatching skill mutations to Gemini Spark runtime tools."""
    skill_name: str
    target_version_id: str
    base_version_id: str
    base_version_hash: str
    proposed_content: str
    diff_preview: str
    change_reason: str
    task_run_id: str
    evidence_ids: list

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SkillBackend(abc.ABC):
    """Abstract interface defining the contract for managing versioned procedural skills."""

    @abc.abstractmethod
    def read_skill(self, skill_name: str, version_id: Optional[str] = None) -> Optional[SkillVersion]:
        """Reads a specific or active skill version."""
        pass

    @abc.abstractmethod
    def write_skill_version(
        self,
        mutation: LearningMutation,
        expected_base_version_id: str,
    ) -> Tuple[bool, str, Optional[SkillVersion]]:
        """Persists a new skill version ensuring base version match and atomic promotion."""
        pass


class LocalFilesystemSkillBackend(SkillBackend):
    """Concrete SkillBackend implementation operating directly on local skills directory via SkillVersionStore."""

    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store

    def read_skill(self, skill_name: str, version_id: Optional[str] = None) -> Optional[SkillVersion]:
        if version_id:
            return self.version_store.get_version(skill_name, version_id)
        return self.version_store.get_active_version(skill_name)

    def write_skill_version(
        self,
        mutation: LearningMutation,
        expected_base_version_id: str,
    ) -> Tuple[bool, str, Optional[SkillVersion]]:
        return self.version_store.append_version(
            skill_name=mutation.target_skill,
            new_content=mutation.proposed_content,
            change_reason=mutation.reason,
            expected_base_version_id=expected_base_version_id,
            task_run_id=mutation.task_run_id,
            diff=mutation.diff,
        )


class SparkRuntimeSkillBridge(SkillBackend):
    """Runtime bridge preparing mutations for execution in live Gemini Spark agent sessions."""

    def __init__(self, local_backend: LocalFilesystemSkillBackend):
        self.local_backend = local_backend
        self.pending_manifests: list[SparkSkillUpdateManifest] = []

    def read_skill(self, skill_name: str, version_id: Optional[str] = None) -> Optional[SkillVersion]:
        return self.local_backend.read_skill(skill_name, version_id)

    def write_skill_version(
        self,
        mutation: LearningMutation,
        expected_base_version_id: str,
    ) -> Tuple[bool, str, Optional[SkillVersion]]:
        active_ver = self.read_skill(mutation.target_skill)
        if not active_ver or active_ver.version_id != expected_base_version_id:
            return False, f"Stale write rejected: expected {expected_base_version_id}, found {active_ver.version_id if active_ver else 'None'}", None

        # Build execution manifest
        manifest = SparkSkillUpdateManifest(
            skill_name=mutation.target_skill,
            target_version_id=f"v{len(self.local_backend.version_store._get_metadata_path(mutation.target_skill)) + 1}",
            base_version_id=expected_base_version_id,
            base_version_hash=mutation.base_version_hash,
            proposed_content=mutation.proposed_content,
            diff_preview=mutation.diff,
            change_reason=mutation.reason,
            task_run_id=mutation.task_run_id,
            evidence_ids=mutation.evidence_ids,
        )
        self.pending_manifests.append(manifest)

        # Apply locally
        return self.local_backend.write_skill_version(mutation, expected_base_version_id)
