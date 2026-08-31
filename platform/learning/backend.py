"""Filesystem and Runtime Storage Backend for Versioned Procedural Skills."""

import json
import os
import shutil
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from platform.learning.contracts import SkillVersion, TaskRun, generate_sha256


class SkillBackend(ABC):
    """Abstract interface for procedural skill storage."""

    @abstractmethod
    def save_version(self, skill_name: str, version: SkillVersion):
        pass

    @abstractmethod
    def get_version(self, skill_name: str, version_id: str) -> Optional[SkillVersion]:
        pass

    @abstractmethod
    def list_versions(self, skill_name: str) -> List[str]:
        pass


class LocalFilesystemSkillBackend(SkillBackend):
    """Local filesystem implementation of SkillBackend storing version manifests in skills/<name>/versions/."""

    def __init__(self, base_skills_dir: Optional[str] = None):
        self.base_skills_dir = base_skills_dir or os.path.expanduser("~/.spark/skills")
        self._lock = threading.Lock()
        os.makedirs(self.base_skills_dir, exist_ok=True)

    def _get_skill_dir(self, skill_name: str) -> str:
        clean = skill_name.split(":", 1)[-1] if ":" in skill_name else skill_name
        return os.path.join(self.base_skills_dir, clean)

    def _get_versions_dir(self, skill_name: str) -> str:
        return os.path.join(self._get_skill_dir(skill_name), "versions")

    def save_version(self, skill_name: str, version: SkillVersion):
        with self._lock:
            vdir = self._get_versions_dir(skill_name)
            os.makedirs(vdir, exist_ok=True)
            vpath = os.path.join(vdir, f"{version.version_id}.json")
            with open(vpath, "w", encoding="utf-8") as f:
                json.dump(version.to_dict(), f, indent=2)

    def get_version(self, skill_name: str, version_id: str) -> Optional[SkillVersion]:
        with self._lock:
            vpath = os.path.join(self._get_versions_dir(skill_name), f"{version_id}.json")
            if not os.path.exists(vpath):
                return None
            with open(vpath, "r", encoding="utf-8") as f:
                return SkillVersion.from_dict(json.load(f))

    def list_versions(self, skill_name: str) -> List[str]:
        with self._lock:
            vdir = self._get_versions_dir(skill_name)
            if not os.path.exists(vdir):
                return []
            versions = []
            for fname in sorted(os.listdir(vdir)):
                if fname.endswith(".json"):
                    versions.append(fname[:-5])
            return versions


class SparkSkillUpdateManifest:
    """Represents a payload prepared for dispatching skill mutations to Gemini Spark runtime tools."""

    def __init__(self, skill_name: str, new_content: str, change_reason: str, version_id: str):
        self.skill_name = skill_name
        self.new_content = new_content
        self.change_reason = change_reason
        self.version_id = version_id
        self.content_hash = generate_sha256(new_content)


class SparkRuntimeSkillBridge:
    """Dispatches skill mutations to external tools when running in live agent environment."""

    def __init__(self, update_skill_tool_fn: Optional[Any] = None):
        self.update_skill_tool_fn = update_skill_tool_fn

    def apply_runtime_mutation(self, manifest: SparkSkillUpdateManifest) -> bool:
        if not self.update_skill_tool_fn:
            return True
        try:
            self.update_skill_tool_fn(
                name=manifest.skill_name,
                content=manifest.new_content,
                description=f"Auto-learned mutation {manifest.version_id}: {manifest.change_reason}",
            )
            return True
        except Exception:
            return False
