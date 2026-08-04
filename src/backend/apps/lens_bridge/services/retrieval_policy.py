"""Retrieval-policy helpers for HFL-managed SourceLens assistants."""

from __future__ import annotations

from typing import Any


def managed_chat_retrieval_policy() -> dict[str, Any]:
    """Return retrieval_policy for HFL Chat / managed KS assistants.

    The Chat workspace is the user's restored data. LensNode skips every path
    component that starts with "." unless include_hidden is true, so enable it.
    Pass empty exclude lists explicitly so LensNode does not fall back to its
    built-in DEFAULT_EXCLUDED_DIRS / DEFAULT_EXCLUDED_EXTENSIONS. Filesystem
    entries "." and ".." are never yielded by directory iteration and need no
    extra rule.
    """
    return {
        "include_hidden": True,
        "exclude_dirs": [],
        "exclude_extensions": [],
    }
