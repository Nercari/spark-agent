from __future__ import annotations
import re
from typing import Dict

class MemoryIdentityAdapter:
    """Privacy-preserving identity adapter that sanitizes PII/user tokens from memory."""

    def __init__(self):
        self.redaction_patterns = [
            (re.compile(r"api[_-]?key[=:\s]+[A-Za-z0-9_\-]+", re.IGNORECASE), "api_key=[REDACTED]"),
            (re.compile(r"bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE), "Bearer [REDACTED]"),
            (re.compile(r"password[=:\s]+[^\s]+", re.IGNORECASE), "password=[REDACTED]"),
        ]

    def sanitize(self, text: str) -> str:
        sanitized = text
        for pattern, replacement in self.redaction_patterns:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized
