"""Declarative Autonomous Memory Platform Module."""

from platform.memory.contracts import (
    MemoryScope,
    MemoryKind,
    MemoryStatus,
    MemoryRecord,
    MemoryClassificationResult,
)
from platform.memory.store import MemoryStore
from platform.memory.retriever import MemoryRetriever
from platform.memory.classifier import MemoryClassifier

__all__ = [
    "MemoryScope",
    "MemoryKind",
    "MemoryStatus",
    "MemoryRecord",
    "MemoryClassificationResult",
    "MemoryStore",
    "MemoryRetriever",
    "MemoryClassifier",
]
