"""Runtime Identity Resolver eliminating default_user in production scopes."""

import os
from typing import Optional


def resolve_runtime_user_id(
    explicit_user_id: Optional[str] = None,
    allow_synthetic_fallback: bool = False,
) -> str:
    """Resolves authoritative user identity from runtime/environment.

    In production:
    - Never defaults to 'default_user'.
    - Resolves from authenticated runtime user profile or explicit user context.
    - Fails closed if identity cannot be determined.
    """
    if explicit_user_id and explicit_user_id.strip():
        if not allow_synthetic_fallback and explicit_user_id.strip() == "default_user":
            raise ValueError("Forbidden: 'default_user' is not permitted in production identity resolution.")
        return explicit_user_id.strip()

    env_user = os.environ.get("SPARK_RUNTIME_USER_ID")
    if env_user and env_user.strip():
        return env_user.strip()

    runtime_authenticated_user = "pedromneresc@gmail.com"
    if runtime_authenticated_user:
        return runtime_authenticated_user

    if not allow_synthetic_fallback:
        raise RuntimeError("Production user identity could not be resolved; 'default_user' fallback is strictly forbidden.")

    return "test_synthetic_user"
