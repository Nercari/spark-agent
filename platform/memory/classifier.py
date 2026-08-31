from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional
from platform.memory.contracts import MemoryType

@dataclass
class ClassificationResult:
    is_salient: bool
    memory_type: MemoryType
    confidence: float

class MemoryClassifier:
    """Classifies conversation text into salient declarative memory categories."""

    def __init__(self):
        self.patterns = [
            (re.compile(r"\b(always|never|prefer|please don't|do not use)\b", re.IGNORECASE), MemoryType.NEGATIVE_CONSTRAINT),
            (re.compile(r"\b(convention|format|style|standard|in this repo|rule)\b", re.IGNORECASE), MemoryType.PROJECT_CONVENTION),
            (re.compile(r"\b(deployed on|version is|host is|environment|port)\b", re.IGNORECASE), MemoryType.ENVIRONMENT_FACT),
            (re.compile(r"\b(my name|i like|i prefer|i want|call me)\b", re.IGNORECASE), MemoryType.USER_PREFERENCE),
        ]

    def classify_text(self, text: str) -> ClassificationResult:
        if not text or len(text.strip()) < 5:
            return ClassificationResult(is_salient=False, memory_type=MemoryType.USER_PREFERENCE, confidence=0.0)

        for pattern, m_type in self.patterns:
            if pattern.search(text):
                return ClassificationResult(is_salient=True, memory_type=m_type, confidence=0.9)

        # Default non-salient for plain dialogue
        return ClassificationResult(is_salient=False, memory_type=MemoryType.USER_PREFERENCE, confidence=0.1)
