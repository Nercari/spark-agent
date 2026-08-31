"""Memory Context Pipeline: Ingestion and Task Context Injection."""

from typing import List, Optional, Tuple
from platform.learning.contracts import TaskRun
from platform.memory.contracts import MemoryRecord, MemoryScope
from platform.memory.store import MemoryStore
from platform.memory.classifier import MemoryClassifier
from platform.memory.retriever import MemoryRetriever


class MemoryContextManager:
    """Manages memory retrieval, relevance gating, and persistence across task lifecycles."""

    def __init__(
        self,
        memory_store: MemoryStore,
        classifier: Optional[MemoryClassifier] = None,
        retriever: Optional[MemoryRetriever] = None,
        allow_synthetic_user_fallback: bool = False,
    ):
        self.memory_store = memory_store
        self.classifier = classifier or MemoryClassifier()
        self.retriever = retriever or MemoryRetriever(memory_store=memory_store)
        self.allow_synthetic_user_fallback = allow_synthetic_user_fallback

    def inject_task_context(
        self,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
        task_goal: Optional[str] = None,
        max_memory_budget: int = 20,
    ) -> Tuple[str, List[MemoryRecord]]:
        effective_user_scope = user_scope_id
        if effective_user_scope is None and self.allow_synthetic_user_fallback:
            effective_user_scope = "usr_synthetic"

        injected = self.retriever.retrieve_task_context_memories(
            project_scope_id=project_scope_id,
            user_scope_id=effective_user_scope,
            task_goal=task_goal,
            max_budget=max_memory_budget,
        )

        lines = ["## Authoritative Context Memories"]
        for m in injected:
            lines.append(f"- [{m.scope.value}:{m.kind.value}] {m.key}: {m.value}")

        context_str = "\n".join(lines)
        return context_str, injected

    def process_task_for_memory_learning(
        self,
        task_run: TaskRun,
    ) -> List[MemoryRecord]:
        extracted = self.classifier.extract_memories_from_task_run(
            task_run,
            default_scope=MemoryScope.PROJECT,
            default_scope_id=task_run.project_scope_id,
        )

        saved = []
        for mem in extracted:
            ok, msg, persisted = self.memory_store.create_or_update_memory(
                scope=mem.scope,
                scope_id=mem.scope_id,
                kind=mem.kind,
                key=mem.key,
                value=mem.value,
                is_trusted_user_origin=True,
                metadata=mem.metadata,
            )
            if ok and persisted:
                saved.append(persisted)

        return saved
