"""Subscription API views (OSS + EE via extend_path)."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

from apps.subscription.api.views.license import LicenseViewSet, health

__all__ = [
    "health",
    "LicenseViewSet",
]
