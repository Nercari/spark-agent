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
    skill_name: str
    base_version_id: str
    base_version_hash: str
    new_version_id: str
    new_version_hash: str
    proposed_content: str
    diff: str
    change_reason: str
    task_run_id: Optional[str] = None
    tool_name: str = "skills:update_skill"
    tool_args: Dict[str, Any] = None

    def __post_init__(self):
        if self.tool_args is None:
            clean_name = self.skill_name.split(":", 1)[-1] if ":" in self.skill_name else self.skill_name
            self.tool_args = {
                "name": clean_name,
                "content": self.proposed_content,
            }


class SkillBackend(abc.ABC):
    @abc.abstractmethod
    def get_skill(self, skill_name: str) -> Optional[SkillVersion]:
        pass

    @abc.abstractmethod
    def apply_mutation(self, mutation: LearningMutation) -> Tuple[bool, str, Optional[SkillVersion]]:
        pass

    @abc.abstractmethod
    def rollback(self, skill_name: str, target_version_id: str, reason: str) -> Tuple[bool, str, Optional[SkillVersion]]:
        pass


class LocalFilesystemSkillBackend(SkillBackend):
    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store

    def get_skill(self, skill_name: str) -> Optional[SkillVersion]:
        return self.version_store.get_active_version(skill_name)

    def apply_mutation(self, mutation: LearningMutation) -> Tuple[bool, str, Optional[SkillVersion]]:
        return self.version_store.create_new_version(
            skill_name=mutation.target_skill,
            base_version_id=mutation.base_version_id,
            base_version_hash=mutation.base_version_hash,
            new_content=mutation.proposed_content,
            change_reason=mutation.reason,
            created_from_task_run_id=mutation.task_run_id,
        )

    def rollback(self, skill_name: str, target_version_id: str, reason: str) -> Tuple[bool, str, Optional[SkillVersion]]:
        return self.version_store.rollback(
            skill_name=skill_name,
            target_version_id=target_version_id,
            reason=reason,
        )


class SparkRuntimeSkillBridge:
    """Bridges the autonomous learning kernel with Spark's real skills:* tool surfaces."""

    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store

    def prepare_mutation_manifest(
        self,
        skill_name: str,
        authoritative_content: str,
        base_version_id: str,
        proposed_content: str,
        change_reason: str,
        task_run_id: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[SparkSkillUpdateManifest]]:
        """Prepares an atomic mutation manifest against the authoritative Spark skill content."""
        current_hash = generate_sha256(authoritative_content)
        new_hash = generate_sha256(proposed_content)

        if current_hash == new_hash:
            return False, "No content changes detected in proposed mutation.", None

        curr_num = int(base_version_id.lstrip("v")) if base_version_id.startswith("v") else 1
        new_version_id = f"v{curr_num + 1}"

        diff_lines = list(
            difflib.unified_diff(
                authoritative_content.splitlines(keepends=True),
                proposed_content.splitlines(keepends=True),
                fromfile=f"{skill_name}:{base_version_id}",
                tofile=f"{skill_name}:{new_version_id}",
            )
        )
        diff_str = "".join(diff_lines)

        manifest = SparkSkillUpdateManifest(
            skill_name=skill_name,
            base_version_id=base_version_id,
            base_version_hash=current_hash,
            new_version_id=new_version_id,
            new_version_hash=new_hash,
            proposed_content=proposed_content,
            diff=diff_str,
            change_reason=change_reason,
            task_run_id=task_run_id,
        )
        return True, "Manifest prepared successfully.", manifest

    def verify_pre_write_state(
        self,
        manifest: SparkSkillUpdateManifest,
        current_authoritative_content: str,
    ) -> Tuple[bool, str]:
        """Validates that the remote authoritative skill content has not drifted prior to write."""
        current_hash = generate_sha256(current_authoritative_content)
        if current_hash != manifest.base_version_hash:
            return (
                False,
                f"Authoritative pre-write stale-write detected: Manifest was generated against "
                f"hash {manifest.base_version_hash[:8]}, but remote skill is currently {current_hash[:8]}.",
            )
        return True, "Pre-write check passed."

    def record_authoritative_commit(
        self,
        manifest: SparkSkillUpdateManifest,
        post_update_content: str,
    ) -> Tuple[bool, str, Optional[SkillVersion]]:
        """Validates authoritative post-update read-back and records the immutable version."""
        post_hash = generate_sha256(post_update_content)
        if post_hash != manifest.new_version_hash:
            return (
                False,
                f"Authoritative read-back verification failed: Expected hash {manifest.new_version_hash[:8]}, got {post_hash[:8]}.",
                None,
            )

        success, msg, new_version = self.version_store.create_new_version(
            skill_name=manifest.skill_name,
            base_version_id=manifest.base_version_id,
            base_version_hash=manifest.base_version_hash,
            new_content=post_update_content,
            change_reason=manifest.change_reason,
            created_from_task_run_id=manifest.task_run_id,
        )
        return success, msg, new_version

    def prepare_rollback_manifest(
        self,
        skill_name: str,
        target_version_id: str,
        reason: str,
    ) -> Tuple[bool, str, Optional[SparkSkillUpdateManifest]]:
        """Prepares a rollback manifest to restore a previous authoritative version."""
        target_version = self.version_store.get_version(skill_name, target_version_id)
        if not target_version:
            return False, f"Target rollback version '{target_version_id}' not found.", None

        active_version = self.version_store.get_active_version(skill_name)
        if not active_version:
            return False, f"Active version not found for '{skill_name}'.", None

        diff_lines = list(
            difflib.unified_diff(
                active_version.content.splitlines(keepends=True),
                target_version.content.splitlines(keepends=True),
                fromfile=f"{skill_name}:{active_version.version_id}",
                tofile=f"{skill_name}:{target_version.version_id}_restored",
            )
        )
        diff_str = "".join(diff_lines)

        manifest = SparkSkillUpdateManifest(
            skill_name=skill_name,
            base_version_id=active_version.version_id,
            base_version_hash=active_version.content_hash,
            new_version_id=f"{target_version.version_id}_restored",
            new_version_hash=target_version.content_hash,
            proposed_content=target_version.content,
            diff=diff_str,
            change_reason=f"Rollback to {target_version_id}: {reason}",
        )
        return True, "Rollback manifest prepared.", manifest
