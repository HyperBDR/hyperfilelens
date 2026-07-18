"""Validate API payloads against registry and value types."""

from __future__ import annotations

import os
from typing import Any

from apps.configuration.exceptions import ConfigValidationError, UnknownConfigKeyError
from apps.configuration.models import GlobalConfig
from apps.configuration.services.internal.registry import registry_by_key


def _strict_registry_enabled() -> bool:
    return os.getenv("CONFIG_STRICT_REGISTRY", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def validate_config_key(key: str) -> None:
    normalized = str(key or "").strip()
    if not normalized:
        raise ConfigValidationError("key is required")
    if " " in normalized:
        raise ConfigValidationError("key must not contain spaces")
    if _strict_registry_enabled() and normalized not in registry_by_key():
        raise UnknownConfigKeyError(f"unknown configuration key: {normalized}")


def validate_value_for_type(*, value: Any, value_type: str) -> None:
    if value_type == GlobalConfig.ValueType.STRING and not isinstance(value, str):
        raise ConfigValidationError("value must be a string")
    if value_type == GlobalConfig.ValueType.NUMBER and not isinstance(
        value, (int, float)
    ):
        raise ConfigValidationError("value must be a number")
    if value_type == GlobalConfig.ValueType.BOOLEAN and not isinstance(value, bool):
        raise ConfigValidationError("value must be a boolean")
    if value_type == GlobalConfig.ValueType.OBJECT and not isinstance(value, dict):
        raise ConfigValidationError("value must be an object")
    if value_type == GlobalConfig.ValueType.ARRAY and not isinstance(value, list):
        raise ConfigValidationError("value must be an array")
