"""Runtime Identity Resolver with honest boundary, opaque ID hashing, and zero hard-coded personal identifiers."""

import os
import hashlib
from typing import Optional, Protocol


class RuntimeIdentityProvider(Protocol):
    """Protocol for resolving authenticated user/profile identity from runtime."""

    def resolve_user_scope_id(self) -> Optional[str]:
        ...


class EnvironmentIdentityProvider:
    """Production identity provider resolving stable user/profile ID from environment or runtime context."""

    def resolve_user_scope_id(self) -> Optional[str]:
        for key in ("SPARK_PROFILE_ID", "SPARK_USER_ID", "SPARK_RUNTIME_USER_ID", "SPARK_AUTH_USER"):
            val = os.environ.get(key)
            if val and val.strip():
                return val.strip()
        return None


class SyntheticTestIdentityProvider:
    """Test provider allowing explicit injection of synthetic test IDs."""

    def __init__(self, test_user_id: str = "test_user_synthetic"):
        self.test_user_id = test_user_id

    def resolve_user_scope_id(self) -> Optional[str]:
        return self.test_user_id


class SparkIdentityRuntimeAdapter:
    """Production adapter converting raw profile metadata into sanitized, opaque stable scope IDs."""

    def __init__(self, raw_profile_id_or_email: Optional[str] = None):
        self.raw_identifier = raw_profile_id_or_email

    def resolve_user_scope_id(self) -> Optional[str]:
        raw = self.raw_identifier or os.environ.get("SPARK_PROFILE_ID") or os.environ.get("SPARK_RUNTIME_USER_ID")
        if not raw or not raw.strip():
            return None
        clean_raw = raw.strip()
        if clean_raw.lower() == "default_user":
            raise ValueError("Forbidden: 'default_user' is not permitted in production identity resolution.")
        hashed = hashlib.sha256(clean_raw.encode("utf-8")).hexdigest()[:16]
        return f"usr_{hashed}"


def resolve_runtime_user_id(
    explicit_user_id: Optional[str] = None,
    provider: Optional[RuntimeIdentityProvider] = None,
    allow_synthetic_fallback: bool = False,
) -> str:
    """Resolves authoritative user identity.

    Enforces:
    1. No hard-coded personal email/account strings in source code.
    2. In production (allow_synthetic_fallback=False), if no identity is supplied, fails closed.
    3. Rejects 'default_user' in production.
    """
    if explicit_user_id and explicit_user_id.strip():
        clean_id = explicit_user_id.strip()
        if not allow_synthetic_fallback and clean_id.lower() == "default_user":
            raise ValueError("Forbidden: 'default_user' is not permitted in production identity resolution.")
        return clean_id

    active_provider = provider or EnvironmentIdentityProvider()
    resolved = active_provider.resolve_user_scope_id()
    if resolved and resolved.strip():
        if not allow_synthetic_fallback and resolved.strip().lower() == "default_user":
            raise ValueError("Forbidden: 'default_user' is not permitted in production identity resolution.")
        return resolved.strip()

    if not allow_synthetic_fallback:
        raise RuntimeError("Production user identity could not be resolved; unauthenticated execution fails closed.")

    return "test_synthetic_user"
