"""DRF helpers for endpoints that must stay public even with stale JWT cookies."""

from rest_framework.permissions import AllowAny


class AnonymousPublicViewMixin:
    """
    Public endpoints that must not fail when the browser still sends an
    expired/invalid access_token cookie (DRF otherwise returns 401 before the view runs).
    """

    authentication_classes = []
    permission_classes = [AllowAny]
