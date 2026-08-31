"""Core data contracts for Declarative Autonomous Memory."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryScope(str, Enum):
    USER = "USER"
    PROJECT = "PROJECT"


class MemoryKind(str, Enum):
    PREFERENCE = "PREFERENCE"
    FACT = "FACT"
    CONVENTION = "CONVENTION"
    ENVIRONMENT = "ENVIRONMENT"
    CORRECTION = "CORRECTION"


class MemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    ARCHIVED = "ARCHIVED"
    SUPERSEDED = "SUPERSEDED"


@dataclass
class MemoryRecord:
    id: str
    scope: MemoryScope
    scope_id: str  # user_id or project_slug
    kind: MemoryKind
    key: str  # Searchable normalized key (e.g. "export_format", "production_region")
    value: Any
    provenance_evidence_ids: List[str]
    created_at: str
    last_confirmed_at: str
    last_used_at: Optional[str] = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    supersedes_memory_id: Optional[str] = None
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


@dataclass
class MemoryClassificationResult:
    is_memory: bool
    kind: Optional[MemoryKind] = None
    scope: Optional[MemoryScope] = None
    scope_id: Optional[str] = None
    key: Optional[str] = None
    value: Optional[Any] = None
    reason: str = ""
    is_procedural_skill: bool = False
