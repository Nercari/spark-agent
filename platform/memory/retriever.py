from __future__ import annotations
import time
from typing import List, Optional
from platform.memory.contracts import DeclarativeMemoryRecord, MemoryStatus
from platform.memory.store import MemoryStore

class MemoryRetriever:
    """Retrieves declarative memory records based on semantic overlap, project scope,
    staleness decay, and utility tracking."""

    def __init__(self, store: MemoryStore):
        self.store = store

    def retrieve(
        self,
        query: str,
        project_scope: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[DeclarativeMemoryRecord]:
        candidates = self.store.list_active(project_scope=project_scope, user_id=user_id)
        if not candidates:
            return []

        query_tokens = set(query.lower().split())
        scored: List[tuple[float, DeclarativeMemoryRecord]] = []

        for record in candidates:
            score = self._compute_relevance_score(record, query_tokens)
            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [record for _, record in scored[:limit]]

    def _compute_relevance_score(
        self,
        record: DeclarativeMemoryRecord,
        query_tokens: set[str],
    ) -> float:
        content_tokens = set(record.content.lower().split())
        overlap = len(query_tokens.intersection(content_tokens))
        if not overlap:
            return 0.0

        base_score = float(overlap)

        # Utility boost for frequently used memories (EXP-05)
        if record.use_count > 0:
            base_score += min(0.5, record.use_count * 0.1)

        # Recency / last used boost
        if record.last_used_at:
            recency = time.time() - record.last_used_at
            if recency < 3600:
                base_score += 0.2

        # Staleness penalty if flagged or conflict history exists
        if record.status == MemoryStatus.REVALIDATION_NEEDED or record.status == MemoryStatus.STALE:
            base_score -= 0.4
        if record.conflict_history:
            base_score -= 0.1 * len(record.conflict_history)

        return max(0.0, base_score)
