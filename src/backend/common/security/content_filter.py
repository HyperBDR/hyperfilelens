"""Content filtering utilities for user-provided text fields."""

import logging
import re

logger = logging.getLogger(__name__)


def contains_filter_words(
    text: str,
    filter_words: list[str],
) -> tuple[bool, str | None]:
    """Return whether ``text`` contains any ``filter_words`` (word boundaries)."""
    if not filter_words or not text:
        return False, None

    text_lower = text.lower()
    for word in filter_words:
        if not word:
            continue

        word_lower = word.lower()
        if " " in word_lower:
            pattern = re.escape(word_lower)
        else:
            escaped_word = re.escape(word_lower)
            pattern = r"\b" + escaped_word + r"(?!-[a-zA-Z])" + r"(?=\W|$)"

        if re.search(pattern, text_lower, re.IGNORECASE):
            return True, word

    return False, None


def check_fields(
    fields: dict[str, str],
    filter_words: list[str],
    item_name: str = "",
) -> tuple[bool, str]:
    """Check whether any field values contain filtered words."""
    if not filter_words:
        return True, ""

    found_fields: list[str] = []
    matched_word: str | None = None

    for field_name, field_text in fields.items():
        if not field_text:
            continue

        contains_word, matched = contains_filter_words(field_text, filter_words)
        if contains_word:
            found_fields.append(field_name)
            if matched_word is None:
                matched_word = matched

    if found_fields:
        location_str = ", ".join(found_fields)
        reason = (
            f"Contains filtered word: '{matched_word}' "
            f"(found in: {location_str})"
        )
        if item_name:
            logger.info("[Content Filter] '%s' filtered: %s", item_name, reason)
        return False, reason

    return True, ""
