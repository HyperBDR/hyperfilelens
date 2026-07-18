"""DRF throttling helpers (framework-level, org-scoped)."""

from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class OrgScopedRateThrottle(SimpleRateThrottle):
    """Rate limit by org key, else authenticated user, else client IP."""

    scope = "org"

    def get_cache_key(self, request, view):
        org_key = (request.META.get("HTTP_X_ORG_KEY") or "").strip()
        if not org_key:
            org_key = (request.query_params.get("org") or "").strip()
        if org_key:
            ident = f"org:{org_key}"
        else:
            user = getattr(request, "user", None)
            if getattr(user, "is_authenticated", False):
                ident = f"user:{getattr(user, 'pk', '')}"
            else:
                ident = f"ip:{self.get_ident(request)}"

        return self.cache_format % {"scope": self.scope, "ident": ident}
