"""Identity resolution runtime adapter with zero personal email dependencies."""

import os
import hashlib
from typing import Optional


def resolve_runtime_user_id(explicit_user_id: Optional[str] = None) -> str:
    """Resolves opaque user identity for declarative scoping without baking personal emails into code."""
    if explicit_user_id and explicit_user_id.strip():
        return explicit_user_id.strip()

    # Fall back to environment variable or stable system hash
    env_user = os.environ.get("SPARK_USER_ID") or os.environ.get("USER") or os.environ.get("USERNAME")
    if env_user:
        # Return hashed stable identifier to ensure privacy and cross-environment stability
        return f"usr_{hashlib.sha256(env_user.encode('utf-8')).hexdigest()[:12]}"

    return "usr_default_spark"
