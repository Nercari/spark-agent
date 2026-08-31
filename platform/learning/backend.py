from __future__ import annotations
import os
import json
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from platform.learning.version_store import VersionStore

class SkillBackend(ABC):
    """Abstract interface for reading, versioning, and mutating procedural skills."""

    @abstractmethod
    def get_skill_content(self, skill_name: str) -> Optional[str]:
        pass

    @abstractmethod
    def apply_mutation(
        self,
        skill_name: str,
        expected_base_version: str,
        new_content: str,
        commit_message: str,
    ) -> bool:
        pass

    @abstractmethod
    def rollback_skill_version(self, skill_name: str, target_version: str) -> bool:
        pass


class LocalFilesystemSkillBackend(SkillBackend):
    """Filesystem-backed skill storage with version tracking."""

    def __init__(self, base_dir: str = "skills"):
        self.base_dir = base_dir
        self.version_store = VersionStore(base_dir=base_dir)

    def get_skill_content(self, skill_name: str) -> Optional[str]:
        skill_file = os.path.join(self.base_dir, skill_name, "SKILL.md")
        if not os.path.isfile(skill_file):
            return None
        with open(skill_file, "r", encoding="utf-8") as f:
            return f.read()

    def apply_mutation(
        self,
        skill_name: str,
        expected_base_version: str,
        new_content: str,
        commit_message: str,
    ) -> bool:
        return self.version_store.commit_new_version(
            skill_name=skill_name,
            expected_base_version=expected_base_version,
            content=new_content,
            commit_message=commit_message,
        )

    def rollback_skill_version(self, skill_name: str, target_version: str) -> bool:
        return self.version_store.rollback_to_version(skill_name, target_version)


class SparkRuntimeSkillBridge:
    """Bridge connecting platform learning engines with runtime skill directories."""

    def __init__(self, backend: SkillBackend):
        self.backend = backend

    def get_runtime_skill(self, skill_name: str) -> Optional[str]:
        return self.backend.get_skill_content(skill_name)
