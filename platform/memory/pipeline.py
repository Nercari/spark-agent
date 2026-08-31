"""Context Injection and Ingestion Pipeline for Declarative Memories."""

from typing import List, Tuple, Optional, Dict, Any
from platform.learning.contracts import TaskRun, EvidenceEvent
from platform.memory.contracts import MemoryRecord, MemoryScope, MemoryKind, MemoryStatus
from platform.memory.store import MemoryStore
from platform.memory.retriever import MemoryRetriever
from platform.memory.classifier import MemoryClassifier


class MemoryContextManager:
    """Orchestrates injection of authoritative declarative memories into task context and post-task ingestion."""

    def __init__(
        self,
        memory_store: MemoryStore,
        retriever: Optional[MemoryRetriever] = None,
        classifier: Optional[MemoryClassifier] = None,
        allow_synthetic_user_fallback: bool = False,
    ):
        self.memory_store = memory_store
        self.retriever = retriever or MemoryRetriever(self.memory_store)
        self.classifier = classifier or MemoryClassifier()
        self.allow_synthetic_user_fallback = allow_synthetic_user_fallback

    def inject_task_context(
        self,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
        task_goal: Optional[str] = None,
        max_memory_budget: int = 20,
    ) -> Tuple[str, List[MemoryRecord]]:
        """Retrieves and formats standing project conventions and user preferences into a bounded prompt block."""
        records = self.retriever.retrieve_task_context_memories(
            project_scope_id=project_scope_id,
            user_scope_id=user_scope_id,
            task_goal=task_goal,
            max_budget=max_memory_budget,
            allow_synthetic_user_fallback=self.allow_synthetic_user_fallback,
        )

        if not records:
            return "", []

        lines = ["# Authoritative Declarative Conventions & Preferences"]
        for r in records:
            scope_tag = f"[{r.scope.value}:{r.scope_id}]" if r.scope == MemoryScope.PROJECT else "[USER]"
            lines.append(f"- {scope_tag} {r.key}: {r.value}")

        return "\n".join(lines), records

    def process_task_for_memory_learning(
        self,
        task_run: TaskRun,
    ) -> List[MemoryRecord]:
        """Extracts and commits new declarative memories from verified task run evidence."""
        proposals = self.classifier.extract_from_task_events(task_run)
        committed_memories = []

        for p in proposals:
            if p.is_memory and p.key and p.value is not None:
                record = self.memory_store.create_or_update_memory(
                    scope=p.scope or MemoryScope.PROJECT,
                    scope_id=p.scope_id or task_run.project_scope_id,
                    kind=p.kind or MemoryKind.CONVENTION,
                    key=p.key,
                    value=p.value,
                    evidence_ids=[e.id for e in task_run.evidence_events],
                    is_trusted_user_origin=True,
                    metadata={"source_task_run_id": task_run.id, "classification_reason": p.reason},
                )
                committed_memories.append(record)

        return committed_memories
