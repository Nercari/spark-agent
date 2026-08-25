"""Hierarchical Memory Retriever for Task Execution Context."""

from typing import Any, Dict, List, Optional, Tuple
from platform.memory.contracts import MemoryRecord
from platform.memory.store import MemoryStore


class MemoryRetriever:
    """Retrieves relevant declarative memories with PROJECT -> USER precedence."""

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def retrieve(
        self,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
        query_keys: Optional[List[str]] = None,
    ) -> Tuple[List[MemoryRecord], Dict[str, Any]]:
        records = self.memory_store.retrieve_for_context(
            project_scope_id=project_scope_id,
            user_scope_id=user_scope_id,
            query_keys=query_keys,
        )
        stats = {
            "retrieved_count": len(records),
            "project_scope_id": project_scope_id,
            "user_scope_id": user_scope_id,
            "keys_queried": query_keys or [],
        }
        return records, stats
