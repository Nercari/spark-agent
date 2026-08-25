"""Automatic Context Injection and Ingestion Pipeline for Declarative Autonomous Memory."""

from typing import Any, Dict, List, Optional, Tuple
from platform.learning.contracts import TaskRun, EventType, TrustClass, is_untrusted_origin
from platform.memory.contracts import MemoryRecord, MemoryScope, MemoryKind, MemoryStatus
from platform.memory.store import MemoryStore
from platform.memory.classifier import MemoryClassifier
from platform.memory.retriever import MemoryRetriever
from platform.memory.identity import resolve_runtime_user_id


class MemoryContextManager:
    """Bridges normal Spark task execution with automatic memory retrieval and ingestion."""

    def __init__(
        self,
        memory_store: Optional[MemoryStore] = None,
        allow_synthetic_user_fallback: bool = False,
    ):
        self.memory_store = memory_store or MemoryStore()
        self.memory_retriever = MemoryRetriever(memory_store=self.memory_store)
        self.allow_synthetic_fallback = allow_synthetic_user_fallback

    def inject_task_context(
        self,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
    ) -> Tuple[str, List[MemoryRecord]]:
        """At task startup: automatically loads relevant active declarative memories into context."""
        effective_user_id = resolve_runtime_user_id(
            explicit_user_id=user_scope_id,
            allow_synthetic_fallback=self.allow_synthetic_fallback,
        )

        records, _ = self.memory_retriever.retrieve(
            project_scope_id=project_scope_id,
            user_scope_id=effective_user_id,
            query_keys=None,
        )

        if not records:
            return "", []

        lines = ["=== Declarative Task Context ==="]
        for rec in records:
            lines.append(f"- [{rec.scope.value}:{rec.key}] = {rec.value} (Kind: {rec.kind.value})")

        context_str = "\n".join(lines)
        return context_str, records

    def process_task_for_memory_learning(self, task_run: TaskRun) -> List[MemoryRecord]:
        """Post-task: automatically identifies and persists declarative facts and records external conflicts."""
        learned_records: List[MemoryRecord] = []
        effective_user_id = resolve_runtime_user_id(
            explicit_user_id=task_run.user_scope_id,
            allow_synthetic_fallback=self.allow_synthetic_fallback,
        )

        for ev in task_run.evidence_events:
            # Path 1: User-Authorized instructions & corrections (Trusted Authority)
            if ev.event_type in {EventType.USER_AUTHORIZED_INSTRUCTION, EventType.USER_CORRECTION}:
                is_trusted = (ev.trust_class == TrustClass.TRUSTED_USER_AUTHORITY)
                classification = MemoryClassifier.classify(
                    text=ev.content,
                    project_scope_id=task_run.project_scope_id,
                    user_scope_id=effective_user_id,
                )

                if classification.is_memory and classification.key and classification.value:
                    new_mem, _, ok, _ = self.memory_store.create_or_update_memory(
                        scope=classification.scope or MemoryScope.PROJECT,
                        scope_id=classification.scope_id or task_run.project_scope_id,
                        kind=classification.kind or MemoryKind.FACT,
                        key=classification.key,
                        value=classification.value,
                        provenance_evidence_ids=[ev.id],
                        is_trusted_user_authority=is_trusted,
                    )
                    if ok and new_mem:
                        learned_records.append(new_mem)

            # Path 2: External tool results & web/email/doc payloads (Conflict Detection Only)
            elif ev.event_type in {EventType.TOOL_RESULT, EventType.EXTERNAL_CONTENT} or is_untrusted_origin(ev.payload_origin):
                classification = MemoryClassifier.classify(
                    text=ev.content,
                    project_scope_id=task_run.project_scope_id,
                    user_scope_id=effective_user_id,
                )
                if classification.is_memory and classification.key and classification.value:
                    target_scope = classification.scope or MemoryScope.PROJECT
                    target_scope_id = classification.scope_id or task_run.project_scope_id
                    self.memory_store.handle_external_conflict(
                        scope=target_scope,
                        scope_id=target_scope_id,
                        key=classification.key,
                        external_value=classification.value,
                        source_evidence_id=ev.id,
                        source_ref=ev.metadata.get("source_ref", f"origin:{ev.payload_origin.value}"),
                    )

        return learned_records
