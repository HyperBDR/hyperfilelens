"""Shared view mixins for org-scoped node API resources."""

from __future__ import annotations

from typing import Any


class SoftDeleteDestroyMixin:
    """Map ``DELETE`` to model ``soft_delete()``."""

    def perform_destroy(self, instance: Any) -> None:
        instance.soft_delete()
