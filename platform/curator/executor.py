from __future__ import annotations
import time
from typing import List, Optional, Dict, Any
from platform.curator.contracts import CuratorAction, CuratorObservation
from platform.learning.backend import SkillBackend
from platform.memory.store import MemoryStore

class CuratorExecutor:
    """Executes curated actions such as auto-rollback on regression or archiving superseded memories."""

    def __init__(self, skill_backend: SkillBackend, memory_store: Optional[MemoryStore] = None):
        self.skill_backend = skill_backend
        self.memory_store = memory_store

    def execute_action(self, action: CuratorAction) -> bool:
        if action.action_type == "ROLLBACK_SKILL":
            skill_name = action.target_id
            target_version = action.parameters.get("target_version")
            if not skill_name or not target_version:
                return False
            # Roll back skill to target version
            return self.skill_backend.rollback_skill_version(skill_name, target_version)

        elif action.action_type == "ARCHIVE_MEMORY":
            if not self.memory_store:
                return False
            memory_id = action.target_id
            rec = self.memory_store.get(memory_id)
            if not rec:
                return False
            rec.status = "ARCHIVED"
            self.memory_store.save(rec)
            return True

        return False
