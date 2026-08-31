"""Identity resolution runtime adapter with zero personal email dependencies."""

import os
from typing import Optional


class IdentityResolutionRuntimeAdapter:
    """Resolves authenticated user scope ID without leaking personal identifiers into codebase."""

    def __init__(self, fallback_scope_id: Optional[str] = None):
        self.fallback_scope_id = fallback_scope_id

    def resolve_active_user_scope_id(self, opaque_authenticated_id: Optional[str] = None) -> Optional[str]:
        if opaque_authenticated_id:
            return opaque_authenticated_id

        env_user = os.environ.get("SPARK_USER_SCOPE_ID")
        if env_user:
            return env_user

        return self.fallback_scope_id
