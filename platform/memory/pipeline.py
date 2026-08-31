"""Memory Context Manager & Ingestion Pipeline with Selective Relevance Gating (EXP-04)."""

from typing import List, Optional, Tuple
from platform.learning.contracts import TaskRun, VerificationStatus
from platform.memory.contracts import MemoryRecord, MemoryScope, MemoryStatus
from platform.memory.store import MemoryStore
from platform.memory.classifier import MemoryClassifier
from platform.memory.retriever import MemoryRetriever


class MemoryContextManager:
    """Coordinates memory injection at task startup and memory extraction at task completion."""

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
        """Retrieves and formats relevant active declarative memories into prompt context string."""
        memories = self.retriever.retrieve_task_context_memories(
            project_scope_id=project_scope_id,
            user_scope_id=user_scope_id,
            task_goal=task_goal,
            max_budget=max_memory_budget,
        )

        if not memories:
            return "", []

        lines = ["## Active Project Conventions & Preferences"]
        for m in memories:
            lines.append(f"- [{m.scope.value}] `{m.key}`: {m.value}")

        context_str = "\n".join(lines) + "\n"
        return context_str, memories

    def process_task_for_memory_learning(
        self,
        task_run: TaskRun,
    ) -> List[MemoryRecord]:
        """Extracts and commits new or updated declarative memory records from a completed task run."""
        learned = self.classifier.extract_memories_from_task_run(
            task_run=task_run,
            default_scope=MemoryScope.PROJECT,
            scope_id=task_run.project_scope_id,
        )

        persisted: List[MemoryRecord] = []
        for mem in learned:
            ok, msg, committed_rec = self.memory_store.create_or_update_memory(
                scope=mem.scope,
                scope_id=mem.scope_id,
                kind=mem.kind,
                key=mem.key,
                value=mem.value,
                confidence=mem.confidence,
                evidence_ids=mem.evidence_ids,
                metadata=mem.metadata,
                is_trusted_user_origin=True,
            )
            if ok and committed_rec:
                persisted.append(committed_rec)

        return persisted
