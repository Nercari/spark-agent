from __future__ import annotations
import os
import json
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class SkillVersionRecord:
    skill_name: str
    version: str
    content: str
    commit_message: str
    timestamp: float

class VersionStore:
    """Append-only version store providing atomic CAS updates for skills."""

    def __init__(self, base_dir: str = "skills"):
        self.base_dir = base_dir

    def get_current_version(self, skill_name: str) -> Optional[str]:
        meta_path = os.path.join(self.base_dir, skill_name, "metadata.json")
        if not os.path.isfile(meta_path):
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("current_version", "v1")
        except Exception:
            return "v1"

    def list_versions(self, skill_name: str) -> List[SkillVersionRecord]:
        versions_dir = os.path.join(self.base_dir, skill_name, "versions")
        if not os.path.isdir(versions_dir):
            return []

        records = []
        for fname in sorted(os.listdir(versions_dir)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(versions_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records.append(SkillVersionRecord(
                    skill_name=skill_name,
                    version=data["version"],
                    content=data["content"],
                    commit_message=data.get("commit_message", ""),
                    timestamp=data.get("timestamp", 0.0),
                ))
            except Exception:
                continue
        return records

    def commit_new_version(
        self,
        skill_name: str,
        expected_base_version: str,
        content: str,
        commit_message: str,
    ) -> bool:
        current = self.get_current_version(skill_name)
        if current and current != expected_base_version:
            return False

        skill_dir = os.path.join(self.base_dir, skill_name)
        versions_dir = os.path.join(skill_dir, "versions")
        os.makedirs(versions_dir, exist_ok=True)

        # Determine next version
        curr_num = int(current[1:]) if current and current.startswith("v") else 1
        next_version = f"v{curr_num + 1}"

        # Write version file
        ver_record = {
            "version": next_version,
            "content": content,
            "commit_message": commit_message,
            "timestamp": time.time(),
        }
        ver_path = os.path.join(versions_dir, f"{next_version}.json")
        with open(ver_path, "w", encoding="utf-8") as f:
            json.dump(ver_record, f, indent=2)

        # Write active SKILL.md
        skill_path = os.path.join(skill_dir, "SKILL.md")
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Update metadata.json
        meta_path = os.path.join(skill_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"skill_name": skill_name, "current_version": next_version, "updated_at": time.time()}, f, indent=2)

        return True

    def rollback_to_version(self, skill_name: str, target_version: str) -> bool:
        versions_dir = os.path.join(self.base_dir, skill_name, "versions")
        ver_path = os.path.join(versions_dir, f"{target_version}.json")
        if not os.path.isfile(ver_path):
            return False

        with open(ver_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        skill_dir = os.path.join(self.base_dir, skill_name)
        skill_path = os.path.join(skill_dir, "SKILL.md")
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(data["content"])

        meta_path = os.path.join(skill_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"skill_name": skill_name, "current_version": target_version, "updated_at": time.time(), "rollback": True}, f, indent=2)

        return True
