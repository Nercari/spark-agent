"""Memory Tracer: Demonstrating Autonomous Declarative Memory Lifecycle & Episodic Retrieval."""

from typing import Dict, Any, List, Optional
from platform.memory.store import MemoryStore
from platform.memory.classifier import MemoryClassifier
from platform.memory.retriever import MemoryRetriever
from platform.memory.contracts import MemoryScope, MemoryKind, MemoryStatus
from platform.episodic.retrieval import EpisodicRetriever
from platform.episodic.contracts import EpisodicQuery


class MemoryTracerRunner:
    def __init__(self, memory_storage_dir: Optional[str] = None, evidence_dir: Optional[str] = None):
        self.memory_store = MemoryStore(base_storage_dir=memory_storage_dir)
        self.memory_retriever = MemoryRetriever(memory_store=self.memory_store)
        self.episodic_retriever = EpisodicRetriever(evidence_dir=evidence_dir)

    def execute_task_1_store_fact(self, user_instruction: str, project_scope_id: str) -> Dict[str, Any]:
        classification = MemoryClassifier.classify(
            text=user_instruction,
            project_scope_id=project_scope_id,
        )
        if classification.is_memory:
            record, _ = self.memory_store.create_or_update_memory(
                scope=classification.scope or MemoryScope.PROJECT,
                scope_id=classification.scope_id or project_scope_id,
                kind=classification.kind or MemoryKind.FACT,
                key=classification.key or "canonical_export_format",
                value=classification.value,
                provenance_evidence_ids=["ev_user_task_1"],
            )
            return {"status": "STORED", "memory": record}
        return {"status": "SKIPPED", "reason": classification.reason}

    def execute_task_2_retrieve_fact(self, project_scope_id: str, query_key: str) -> Dict[str, Any]:
        memories, stats = self.memory_retriever.retrieve(
            project_scope_id=project_scope_id,
            query_keys=[query_key],
        )
        if memories:
            return {"status": "RETRIEVED", "active_value": memories[0].value, "stats": stats}
        return {"status": "NOT_FOUND", "stats": stats}

    def execute_correction_supersede(self, user_correction: str, project_scope_id: str) -> Dict[str, Any]:
        classification = MemoryClassifier.classify(
            text=user_correction,
            project_scope_id=project_scope_id,
        )
        if classification.is_memory:
            new_record, old_record = self.memory_store.create_or_update_memory(
                scope=classification.scope or MemoryScope.PROJECT,
                scope_id=classification.scope_id or project_scope_id,
                kind=classification.kind or MemoryKind.CORRECTION,
                key=classification.key or "canonical_export_format",
                value=classification.value,
                provenance_evidence_ids=["ev_user_correction"],
            )
            return {
                "status": "SUPERSEDED",
                "new_memory": new_record,
                "old_memory": old_record,
            }
        return {"status": "FAILED", "reason": classification.reason}

    def test_external_contradiction_protection(
        self,
        project_scope_id: str,
        query_key: str,
        untrusted_value: str,
        source_evidence_id: str,
    ) -> Dict[str, Any]:
        overwritten, msg, active_mem = self.memory_store.handle_external_conflict(
            scope=MemoryScope.PROJECT,
            scope_id=project_scope_id,
            key=query_key,
            external_value=untrusted_value,
            source_evidence_id=source_evidence_id,
            source_ref="https://untrusted-doc.example.com",
        )
        return {"overwritten": overwritten, "message": msg, "active_value": active_mem.value if active_mem else None}

    def test_project_isolation(self, project_b_id: str, query_key: str) -> Dict[str, Any]:
        memories, stats = self.memory_retriever.retrieve(
            project_scope_id=project_b_id,
            query_keys=[query_key],
        )
        return {"leaked": len(memories) > 0, "memories": memories, "stats": stats}

    def test_episodic_search(self, skill_name: Optional[str] = None) -> Dict[str, Any]:
        query = EpisodicQuery(skill_name=skill_name, limit=5)
        summaries = self.episodic_retriever.search_task_runs(query)
        return {"count": len(summaries), "summaries": [s.to_dict() for s in summaries]}
