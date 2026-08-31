from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

class MemoryType(str, Enum):
    USER_PREFERENCE = "USER_PREFERENCE"
    PROJECT_CONVENTION = "PROJECT_CONVENTION"
    ENVIRONMENT_FACT = "ENVIRONMENT_FACT"
    NEGATIVE_CONSTRAINT = "NEGATIVE_CONSTRAINT"

class MemoryScope(str, Enum):
    USER = "USER"
    PROJECT = "PROJECT"
    GLOBAL = "GLOBAL"

class MemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REVALIDATION_NEEDED = "REVALIDATION_NEEDED"
    STALE = "STALE"
    ARCHIVED = "ARCHIVED"

class MemorySource(str, Enum):
    CONVERSATION = "CONVERSATION"
    EXPLICIT_CORRECTION = "EXPLICIT_CORRECTION"
    SYSTEM_INSPECTION = "SYSTEM_INSPECTION"
    UNTRUSTED_WEB = "UNTRUSTED_WEB"

@dataclass
class DeclarativeMemoryRecord:
    content: str
    memory_type: MemoryType
    scope: MemoryScope = MemoryScope.PROJECT
    source: MemorySource = MemorySource.CONVERSATION
    status: MemoryStatus = MemoryStatus.ACTIVE
    project_scope: Optional[str] = None
    user_id: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    last_used_at: Optional[float] = None
    use_count: int = 0
    superseded_by: Optional[str] = None
    confidence: float = 1.0
    conflict_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value if isinstance(self.memory_type, Enum) else self.memory_type,
            "scope": self.scope.value if isinstance(self.scope, Enum) else self.scope,
            "source": self.source.value if isinstance(self.source, Enum) else self.source,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "project_scope": self.project_scope,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used_at": self.last_used_at,
            "use_count": self.use_count,
            "superseded_by": self.superseded_by,
            "confidence": self.confidence,
            "conflict_history": self.conflict_history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DeclarativeMemoryRecord:
        return cls(
            id=data.get("id"),
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            scope=MemoryScope(data.get("scope", "PROJECT")),
            source=MemorySource(data.get("source", "CONVERSATION")),
            status=MemoryStatus(data.get("status", "ACTIVE")),
            project_scope=data.get("project_scope"),
            user_id=data.get("user_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            last_used_at=data.get("last_used_at"),
            use_count=data.get("use_count", 0),
            superseded_by=data.get("superseded_by"),
            confidence=data.get("confidence", 1.0),
            conflict_history=data.get("conflict_history", []),
        )
