"""Memory Retriever with Utility-Aware Ranking & Selective Relevance Gating (EXP-04 & EXP-05)."""

import math
from datetime import datetime, timezone
from typing import List, Optional
from platform.memory.contracts import MemoryRecord, MemoryScope, MemoryStatus
from platform.memory.store import MemoryStore


class MemoryRetriever:
    """Retrieves and ranks active declarative memories based on relevance, utility, and recency/staleness."""

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def _compute_utility_score(self, memory: MemoryRecord, task_goal: Optional[str] = None) -> float:
        score = float(memory.confidence)

        # Usage & verification boost
        score += min(memory.use_count * 0.2, 1.0)

        # Relevance scoring with goal keywords
        if task_goal:
            goal_lower = task_goal.lower()
            key_clean = memory.key.replace("_", " ").lower()
            if any(term in goal_lower for term in key_clean.split()):
                score += 1.5
            if str(memory.value).lower() in goal_lower:
                score += 1.0

        # Scope precedence: Project scope outranks User scope on conflicting keys
        if memory.scope == MemoryScope.PROJECT:
            score += 0.5

        # Staleness decay penalty (EXP-05) if memory hasn't been used and has accumulated conflicts
        conflicts = memory.metadata.get("candidate_conflicts", [])
        if len(conflicts) > 0:
            score -= (len(conflicts) * 0.4)

        return score

    def retrieve_task_context_memories(
        self,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
        task_goal: Optional[str] = None,
        max_budget: int = 20,
    ) -> List[MemoryRecord]:
        records: List[MemoryRecord] = []

        if project_scope_id:
            proj_mems = self.memory_store.retrieve_memories(
                scope=MemoryScope.PROJECT,
                scope_id=project_scope_id,
                status=MemoryStatus.ACTIVE,
            )
            records.extend(proj_mems)

        if user_scope_id:
            user_mems = self.memory_store.retrieve_memories(
                scope=MemoryScope.USER,
                scope_id=user_scope_id,
                status=MemoryStatus.ACTIVE,
            )
            records.extend(user_mems)

        # Deduplicate on key prioritizing higher authority (Project > User)
        key_map = {}
        for r in records:
            if r.key not in key_map:
                key_map[r.key] = r
            else:
                existing = key_map[r.key]
                if existing.scope == MemoryScope.USER and r.scope == MemoryScope.PROJECT:
                    key_map[r.key] = r

        deduped = list(key_map.values())
        scored = [(r, self._compute_utility_score(r, task_goal=task_goal)) for r in deduped]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [r for r, score in scored[:max_budget]]
