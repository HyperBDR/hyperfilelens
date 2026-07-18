from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldError:
    field: str
    code: str
    message: str = ""


@dataclass
class AppError(Exception):
    """Structured application error mapped to Problem Details + Registry codes."""

    code: str
    status: int = 400
    retryable: bool = False
    severity: str = "error"
    meta: dict[str, Any] = field(default_factory=dict)
    diagnostic: str = ""
    field_errors: list[FieldError] = field(default_factory=list)
    title: str = ""

    def __str__(self) -> str:
        return self.diagnostic or self.code
