"""Skill Version Store: Versioned Append-Only Storage & Atomic Mutation Management."""

import json
import os
import shutil
import threading
from typing import Dict, List, Optional, Tuple
from platform.learning.contracts import (
    SkillVersion,
    generate_sha256,
)


class SkillVersionStore:
    """Manages versioned, append-only procedural skill packages with atomic CAS pointer switches."""

    def __init__(self, base_skills_dir: Optional[str] = None):
        self.base_skills_dir = base_skills_dir or os.path.expanduser("~/.spark/skills")
        self._lock = threading.Lock()
        os.makedirs(self.base_skills_dir, exist_ok=True)

    def _get_skill_dir(self, skill_name: str) -> str:
        clean_name = skill_name.split(":", 1)[-1] if ":" in skill_name else skill_name
        return os.path.join(self.base_skills_dir, clean_name)

    def _get_metadata_path(self, skill_name: str) -> str:
        return os.path.join(self._get_skill_dir(skill_name), "metadata.json")

    def _get_versions_dir(self, skill_name: str) -> str:
        return os.path.join(self._get_skill_dir(skill_name), "versions")

    def initialize_skill_version(
        self,
        skill_name: str,
        initial_content: str,
        change_reason: str = "Initial baseline",
    ) -> SkillVersion:
        with self._lock:
            sdir = self._get_skill_dir(skill_name)
            vdir = self._get_versions_dir(skill_name)
            os.makedirs(vdir, exist_ok=True)

            mpath = self._get_metadata_path(skill_name)
            if os.path.exists(mpath):
                with open(mpath, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                active_id = meta.get("active_version_id", "v1")
                return self.get_version(skill_name, active_id)

            c_hash = generate_sha256(initial_content)
            v1_ver = SkillVersion(
                version_id="v1",
                skill_name=skill_name,
                parent_version_id=None,
                content=initial_content,
                content_hash=c_hash,
                created_at="2026-08-25T00:00:00Z",
                change_reason=change_reason,
                status="active",
            )

            # 1. Save v1 version file
            v1_path = os.path.join(vdir, "v1.json")
            with open(v1_path, "w", encoding="utf-8") as f:
                json.dump(v1_ver.to_dict(), f, indent=2)

            # 2. Write active SKILL.md
            skill_md_path = os.path.join(sdir, "SKILL.md")
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(initial_content)

            # 3. Write metadata.json
            meta_dict = {
                "skill_name": skill_name,
                "active_version_id": "v1",
                "versions": ["v1"],
            }
            with open(mpath, "w", encoding="utf-8") as f:
                json.dump(meta_dict, f, indent=2)

            return v1_ver

    def get_current_skill_content(self, skill_name: str) -> Optional[str]:
        sdir = self._get_skill_dir(skill_name)
        skill_md_path = os.path.join(sdir, "SKILL.md")
        if not os.path.exists(skill_md_path):
            return None
        with open(skill_md_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_active_version_id(self, skill_name: str) -> Optional[str]:
        mpath = self._get_metadata_path(skill_name)
        if not os.path.exists(mpath):
            return None
        with open(mpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("active_version_id")

    def get_version(self, skill_name: str, version_id: str) -> Optional[SkillVersion]:
        vpath = os.path.join(self._get_versions_dir(skill_name), f"{version_id}.json")
        if not os.path.exists(vpath):
            return None
        with open(vpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return SkillVersion.from_dict(data)

    def append_version(
        self,
        skill_name: str,
        new_content: str,
        change_reason: str,
        expected_base_version_id: str,
        task_run_id: Optional[str] = None,
        diff: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[SkillVersion]]:
        with self._lock:
            mpath = self._get_metadata_path(skill_name)
            if not os.path.exists(mpath):
                return False, f"Skill {skill_name} not initialized.", None

            with open(mpath, "r", encoding="utf-8") as f:
                meta = json.load(f)

            active_ver = meta.get("active_version_id")
            if active_ver != expected_base_version_id:
                return False, f"Stale write rejected: expected base {expected_base_version_id}, found {active_ver}.", None

            versions = meta.get("versions", [])
            next_idx = len(versions) + 1
            new_version_id = f"v{next_idx}"

            vdir = self._get_versions_dir(skill_name)
            vpath = os.path.join(vdir, f"{new_version_id}.json")
            if os.path.exists(vpath):
                return False, f"Version overwrite rejected: {new_version_id} already exists.", None

            c_hash = generate_sha256(new_content)
            new_ver = SkillVersion(
                version_id=new_version_id,
                skill_name=skill_name,
                parent_version_id=active_ver,
                content=new_content,
                content_hash=c_hash,
                created_at="2026-08-25T12:00:00Z",
                created_from_task_run_id=task_run_id,
                change_reason=change_reason,
                diff=diff,
                status="active",
            )

            # 1. Write immutable version file
            with open(vpath, "w", encoding="utf-8") as f:
                json.dump(new_ver.to_dict(), f, indent=2)

            # 2. Write active SKILL.md
            sdir = self._get_skill_dir(skill_name)
            skill_md_path = os.path.join(sdir, "SKILL.md")
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # 3. Update metadata.json atomic switch
            versions.append(new_version_id)
            meta["active_version_id"] = new_version_id
            meta["versions"] = versions
            with open(mpath, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            return True, f"Successfully promoted {new_version_id}", new_ver

    def rollback_version(
        self,
        skill_name: str,
        target_version_id: str,
    ) -> Tuple[bool, str]:
        with self._lock:
            mpath = self._get_metadata_path(skill_name)
            if not os.path.exists(mpath):
                return False, f"Skill {skill_name} not initialized."

            with open(mpath, "r", encoding="utf-8") as f:
                meta = json.load(f)

            vdir = self._get_versions_dir(skill_name)
            vpath = os.path.join(vdir, f"{target_version_id}.json")
            if not os.path.exists(vpath):
                return False, f"Target version {target_version_id} does not exist."

            with open(vpath, "r", encoding="utf-8") as f:
                vdata = json.load(f)
                target_content = vdata["content"]

            sdir = self._get_skill_dir(skill_name)
            skill_md_path = os.path.join(sdir, "SKILL.md")
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(target_content)

            meta["active_version_id"] = target_version_id
            with open(mpath, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            return True, f"Successfully rolled back {skill_name} to {target_version_id}"
