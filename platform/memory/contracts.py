"""Contracts and domain models for Declarative Memory system."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryScope(str, Enum):
    PROJECT = "PROJECT"
    USER = "USER"


class MemoryKind(str, Enum):
    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    CONVENTION = "CONVENTION"
    ENVIRONMENT = "ENVIRONMENT"
    CORRECTION = "CORRECTION"


class MemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"
    RETRACTED = "RETRACTED"


@dataclass
class MemoryRecord:
    id: str
    scope: MemoryScope
    scope_id: str
    kind: MemoryKind
    key: str
    value: Any
    status: MemoryStatus = MemoryStatus.ACTIVE
    confidence: float = 1.0
    revision: int = 1
    created_at: str = ""
    updated_at: str = ""
    last_confirmed_at: str = ""
    last_used_at: Optional[str] = None
    use_count: int = 0
    evidence_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scope"] = self.scope.value
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        d = data.copy()
        d["scope"] = MemoryScope(d["scope"])
        d["kind"] = MemoryKind(d["kind"])
        d["status"] = MemoryStatus(d["status"])
        return cls(**d)
