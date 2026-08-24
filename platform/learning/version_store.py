"""Immutable Skill Version Store with Strict Diff Integrity and Rollback Management."""

import os
import json
import difflib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from platform.learning.contracts import SkillVersion, generate_sha256


class SkillVersionStore:
    def __init__(self, base_skills_dir: str = "/working_dir/c_b490a8c7dd21c813/skills"):
        self.base_skills_dir = base_skills_dir
        os.makedirs(self.base_skills_dir, exist_ok=True)

    def _get_skill_dir(self, skill_name: str) -> str:
        clean_name = skill_name.split(":", 1)[-1] if ":" in skill_name else skill_name
        return os.path.join(self.base_skills_dir, clean_name)

    def _get_versions_dir(self, skill_name: str) -> str:
        versions_dir = os.path.join(self._get_skill_dir(skill_name), "versions")
        os.makedirs(versions_dir, exist_ok=True)
        return versions_dir

    def _get_metadata_path(self, skill_name: str) -> str:
        return os.path.join(self._get_skill_dir(skill_name), "metadata.json")

    def initialize_skill_version(
        self, skill_name: str, initial_content: str, change_reason: str = "Initial version"
    ) -> SkillVersion:
        """Initializes v1 for a newly registered or existing skill."""
        skill_dir = self._get_skill_dir(skill_name)
        os.makedirs(skill_dir, exist_ok=True)

        v1 = SkillVersion(
            version_id="v1",
            skill_name=skill_name,
            parent_version_id=None,
            content=initial_content,
            content_hash=generate_sha256(initial_content),
            created_at=datetime.now(timezone.utc).isoformat(),
            created_from_task_run_id=None,
            change_reason=change_reason,
            diff=None,
            status="active",
        )

        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(initial_content)

        self._save_version_record(v1)

        self._write_metadata(
            skill_name=skill_name,
            active_version_id="v1",
            active_version_hash=v1.content_hash,
            history=["v1"],
        )
        return v1

    def get_active_version(self, skill_name: str) -> Optional[SkillVersion]:
        meta_path = self._get_metadata_path(skill_name)
        if not os.path.exists(meta_path):
            skill_md_path = os.path.join(self._get_skill_dir(skill_name), "SKILL.md")
            if os.path.exists(skill_md_path):
                with open(skill_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return self.initialize_skill_version(skill_name, content, "Auto-initialized from existing SKILL.md")
            return None

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        active_id = meta["active_version_id"]
        return self.get_version(skill_name, active_id)

    def get_version(self, skill_name: str, version_id: str) -> Optional[SkillVersion]:
        v_path = os.path.join(self._get_versions_dir(skill_name), f"{version_id}.json")
        if not os.path.exists(v_path):
            return None
        with open(v_path, "r", encoding="utf-8") as f:
            return SkillVersion.from_dict(json.load(f))

    def create_new_version(
        self,
        skill_name: str,
        base_version_id: str,
        base_version_hash: str,
        new_content: str,
        change_reason: str,
        created_from_task_run_id: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[SkillVersion]]:
        """Creates a new version following read-before-write validation and canonical diff computation."""
        active = self.get_active_version(skill_name)
        if not active:
            return False, f"Skill '{skill_name}' does not exist.", None

        if active.version_id != base_version_id or active.content_hash != base_version_hash:
            return (
                False,
                f"Stale-write rejected: Base version {base_version_id} ({base_version_hash[:8]}) "
                f"does not match current active version {active.version_id} ({active.content_hash[:8]}).",
                None,
            )

        current_num = int(active.version_id.lstrip("v")) if active.version_id.startswith("v") else 1
        new_version_id = f"v{current_num + 1}"

        # Canonical unified diff recomputation
        diff_lines = list(
            difflib.unified_diff(
                active.content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"{skill_name}:{active.version_id}",
                tofile=f"{skill_name}:{new_version_id}",
            )
        )
        diff_str = "".join(diff_lines)

        new_version = SkillVersion(
            version_id=new_version_id,
            skill_name=skill_name,
            parent_version_id=active.version_id,
            content=new_content,
            content_hash=generate_sha256(new_content),
            created_at=datetime.now(timezone.utc).isoformat(),
            created_from_task_run_id=created_from_task_run_id,
            change_reason=change_reason,
            diff=diff_str,
            status="active",
        )

        if not new_version.validate_diff_integrity(active):
            return False, "Diff integrity validation failed: computed diff does not match version content.", None

        active.status = "superseded"
        self._save_version_record(active)
        self._save_version_record(new_version)

        skill_md_path = os.path.join(self._get_skill_dir(skill_name), "SKILL.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        meta = self._read_metadata(skill_name)
        history = meta.get("history", [])
        if new_version_id not in history:
            history.append(new_version_id)
        self._write_metadata(
            skill_name=skill_name,
            active_version_id=new_version_id,
            active_version_hash=new_version.content_hash,
            history=history,
        )
        return True, "Successfully created and activated new version.", new_version

    def rollback(self, skill_name: str, target_version_id: str, reason: str) -> Tuple[bool, str, Optional[SkillVersion]]:
        """Rolls back the active skill to a previously saved version."""
        target_version = self.get_version(skill_name, target_version_id)
        if not target_version:
            return False, f"Target version {target_version_id} not found for skill {skill_name}.", None

        active = self.get_active_version(skill_name)
        if active:
            active.status = "rolled_back"
            self._save_version_record(active)

        target_version.status = "active"
        target_version.change_reason = f"Rolled back to {target_version_id}: {reason}"
        self._save_version_record(target_version)

        skill_md_path = os.path.join(self._get_skill_dir(skill_name), "SKILL.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(target_version.content)

        meta = self._read_metadata(skill_name)
        self._write_metadata(
            skill_name=skill_name,
            active_version_id=target_version_id,
            active_version_hash=target_version.content_hash,
            history=meta.get("history", []),
        )
        return True, f"Successfully rolled back to {target_version_id}.", target_version

    def validate_all_versions_diff_integrity(self, skill_name: str) -> Tuple[bool, List[str]]:
        """Validates that every historical version of a skill has canonical diff integrity."""
        meta = self._read_metadata(skill_name)
        history = meta.get("history", [])
        errors = []

        for vid in history:
            ver = self.get_version(skill_name, vid)
            if not ver:
                errors.append(f"Version {vid} missing from store.")
                continue
            if ver.parent_version_id:
                parent = self.get_version(skill_name, ver.parent_version_id)
                if not parent:
                    errors.append(f"Parent version {ver.parent_version_id} missing for {vid}.")
                    continue
                if not ver.validate_diff_integrity(parent):
                    errors.append(f"Diff mismatch on version {vid} against parent {ver.parent_version_id}.")

        return len(errors) == 0, errors

    def _save_version_record(self, version: SkillVersion):
        v_path = os.path.join(self._get_versions_dir(version.skill_name), f"{version.version_id}.json")
        with open(v_path, "w", encoding="utf-8") as f:
            json.dump(version.to_dict(), f, indent=2)

    def _read_metadata(self, skill_name: str) -> Dict:
        path = self._get_metadata_path(skill_name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"skill_name": skill_name, "history": []}

    def _write_metadata(self, skill_name: str, active_version_id: str, active_version_hash: str, history: List[str]):
        meta = {
            "skill_name": skill_name,
            "active_version_id": active_version_id,
            "active_version_hash": active_version_hash,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "history": history,
        }
        with open(self._get_metadata_path(skill_name), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
