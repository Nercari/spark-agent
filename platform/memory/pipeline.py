from __future__ import annotations
from typing import List, Optional, Dict, Any
from platform.memory.contracts import (
    DeclarativeMemoryRecord,
    MemoryType,
    MemoryScope,
    MemorySource,
    MemoryStatus,
)
from platform.memory.store import MemoryStore
from platform.memory.retriever import MemoryRetriever
from platform.memory.classifier import MemoryClassifier
from platform.memory.identity import MemoryIdentityAdapter

class MemoryPipeline:
    """End-to-end memory pipeline orchestrating classification, store persistence,
    identity/privacy filtering, and relevance retrieval."""

    def __init__(
        self,
        store: MemoryStore,
        retriever: Optional[MemoryRetriever] = None,
        classifier: Optional[MemoryClassifier] = None,
        identity_adapter: Optional[MemoryIdentityAdapter] = None,
    ):
        self.store = store
        self.retriever = retriever or MemoryRetriever(store)
        self.classifier = classifier or MemoryClassifier()
        self.identity_adapter = identity_adapter or MemoryIdentityAdapter()

    def process_observation(
        self,
        raw_text: str,
        source: MemorySource = MemorySource.CONVERSATION,
        project_scope: Optional[str] = None,
        user_id: Optional[str] = None,
        authoritative: bool = True,
    ) -> Optional[DeclarativeMemoryRecord]:
        """Classify raw interaction observation and persist if salient."""
        classification = self.classifier.classify_text(raw_text)
        if not classification.is_salient:
            return None

        # Fail closed on untrusted sources attempting to create declarative records
        if not authoritative or source == MemorySource.UNTRUSTED_WEB:
            return None

        # Privacy / identity adaptation
        anonymized_text = self.identity_adapter.sanitize(raw_text)

        scope = MemoryScope.PROJECT if project_scope else MemoryScope.USER

        record = DeclarativeMemoryRecord(
            content=anonymized_text,
            memory_type=classification.memory_type,
            scope=scope,
            source=source,
            status=MemoryStatus.ACTIVE,
            project_scope=project_scope,
            user_id=user_id,
            confidence=classification.confidence,
        )

        return self.store.save(record)

    def retrieve_context(
        self,
        query: str,
        project_scope: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[DeclarativeMemoryRecord]:
        """Retrieve relevant active memory records with scope isolation."""
        return self.retriever.retrieve(
            query=query,
            project_scope=project_scope,
            user_id=user_id,
            limit=limit,
        )
