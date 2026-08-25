"""Declarative Autonomous Memory Platform Module."""

from platform.memory.contracts import (
    MemoryScope,
    MemoryKind,
    MemoryStatus,
    MemoryRecord,
    MemoryClassificationResult,
)
from platform.memory.backend import (
    MemoryBackend,
    SqliteMemoryBackend,
    LocalFilesystemMemoryBackend,
    DurableSparkMemoryBackend,
)
from platform.memory.store import MemoryStore
from platform.memory.retriever import MemoryRetriever
from platform.memory.classifier import MemoryClassifier
from platform.memory.pipeline import MemoryContextManager
from platform.memory.identity import resolve_runtime_user_id

__all__ = [
    "MemoryScope",
    "MemoryKind",
    "MemoryStatus",
    "MemoryRecord",
    "MemoryClassificationResult",
    "MemoryBackend",
    "SqliteMemoryBackend",
    "LocalFilesystemMemoryBackend",
    "DurableSparkMemoryBackend",
    "MemoryStore",
    "MemoryRetriever",
    "MemoryClassifier",
    "MemoryContextManager",
    "resolve_runtime_user_id",
]
