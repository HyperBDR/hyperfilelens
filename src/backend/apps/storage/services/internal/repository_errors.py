from __future__ import annotations

import re
from typing import Any


REPOSITORY_ALREADY_EXISTS_CODE = "STORAGE.REPOSITORY_ALREADY_EXISTS"
REPOSITORY_ALREADY_EXISTS_MESSAGE = (
    "A Kopia repository already exists at the selected location. "
    "Import is not supported in this version. Choose a different storage location."
)


class RepositoryAlreadyExistsError(RuntimeError):
    """Raised when strict repository initialization finds an existing repository."""


_REPOSITORY_CONFLICT_MARKERS = (
    "already exists",
    "already initialized",
    "repository exists",
    "found existing data in storage location",
)
_GENERIC_EXIT_MESSAGE = re.compile(
    r"^(?:exit\s+\d+\s*:\s*)?(?:exit status\s+\d+|exit\s+\d+)$",
    re.IGNORECASE,
)


def _agent_repository_command_messages(result: Any) -> list[str]:
    if not isinstance(result, dict):
        return []
    messages: list[str] = []
    for command_key in ("repository_create", "repository_connect", "repository_status"):
        command_result = result.get(command_key)
        if not isinstance(command_result, dict):
            continue
        for output_key in ("stderr_tail", "stderr", "stdout_tail", "stdout"):
            message = str(command_result.get(output_key) or "").strip()
            if message and message not in messages:
                messages.append(message)
    for output_key in ("error", "stderr", "detail"):
        message = str(result.get(output_key) or "").strip()
        if message and message not in messages:
            messages.append(message)
    return messages


def agent_result_has_repository_conflict(result: Any) -> bool:
    if (
        isinstance(result, dict)
        and str(result.get("error_code") or "").strip() == REPOSITORY_ALREADY_EXISTS_CODE
    ):
        return True
    if not isinstance(result, dict) or not isinstance(result.get("repository_create"), dict):
        return False
    create_result = result["repository_create"]
    output = "\n".join(
        str(create_result.get(key) or "").strip()
        for key in ("stderr_tail", "stderr", "stdout_tail", "stdout")
    ).lower()
    return any(marker in output for marker in _REPOSITORY_CONFLICT_MARKERS)


def agent_repository_failure_message(result: Any, *, last_error: str = "") -> str:
    """Prefer captured repository command output over a generic process exit."""

    fallback = str(last_error or "").strip()
    if fallback and not _GENERIC_EXIT_MESSAGE.fullmatch(fallback):
        return fallback
    messages = _agent_repository_command_messages(result)
    if messages:
        return messages[0]
    return fallback
