"""Declarative Memory Retrieval Engine (EXP-04 Relevance Scoring & EXP-05 Staleness Penalties)."""

from typing import List, Optional
from platform.memory.contracts import MemoryRecord, MemoryScope, MemoryKind, MemoryStatus
from platform.memory.store import MemoryStore


class MemoryRetriever:
    """Retrieves active declarative memories prioritized by task-goal relevance, recency, and utility."""

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def _compute_relevance_score(self, record: MemoryRecord, task_goal: Optional[str] = None) -> float:
        score = 0.0

        # Universal conventions and preferences have high base utility
        if record.kind in [MemoryKind.CONVENTION, MemoryKind.PREFERENCE]:
            score += 1.0
        elif record.kind in [MemoryKind.ENVIRONMENT, MemoryKind.FACT]:
            score += 0.5

        # Goal token match boost
        if task_goal:
            goal_tokens = set(task_goal.lower().split())
            key_tokens = set(record.key.lower().replace("_", " ").split())
            val_tokens = set(str(record.value).lower().replace("_", " ").split())
            if (key_tokens | val_tokens) & goal_tokens:
                score += 0.8

        # Recency utility boost
        if record.last_used_at:
            score += 0.2

        # Staleness & conflict penalties (EXP-05)
        conflicts = record.metadata.get("candidate_conflicts", [])
        if conflicts:
            score -= (len(conflicts) * 0.1)

        if record.status == MemoryStatus.STALE or record.metadata.get("revalidation_needed"):
            score -= 0.4

        return score

    def retrieve_task_context_memories(
        self,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
        task_goal: Optional[str] = None,
        max_budget: int = 20,
        allow_synthetic_user_fallback: bool = False,
    ) -> List[MemoryRecord]:
        candidates: List[MemoryRecord] = []

        if project_scope_id:
            candidates.extend(self.memory_store.retrieve_memories(
                scope=MemoryScope.PROJECT,
                scope_id=project_scope_id,
                status=MemoryStatus.ACTIVE,
            ))

        if user_scope_id:
            candidates.extend(self.memory_store.retrieve_memories(
                scope=MemoryScope.USER,
                scope_id=user_scope_id,
                status=MemoryStatus.ACTIVE,
            ))
        elif allow_synthetic_user_fallback:
            candidates.extend(self.memory_store.retrieve_memories(
                scope=MemoryScope.USER,
                scope_id="usr_synthetic",
                status=MemoryStatus.ACTIVE,
            ))

        scored = [(m, self._compute_relevance_score(m, task_goal)) for m in candidates]
        scored.sort(key=lambda x: (x[1], x[0].created_at), reverse=True)

        return [x[0] for x in scored[:max_budget]]
