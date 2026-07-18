"""
Backward-compatible imports.

Prefer ``apps.configuration.selectors.interface``.
"""

from apps.configuration.selectors.interface import (
    get_config,
    invalidate_config_cache,
)

__all__ = ["get_config", "invalidate_config_cache"]
