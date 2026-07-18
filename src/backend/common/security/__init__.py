"""Runtime content-safety primitives (e.g. sensitive-word checks).

Opt-in per view or serializer; not applied globally via middleware.

For TLS, cookies, and reverse-proxy hardening, see ``project.settings.security``
(imported from ``project.settings.base``), not this package.
"""

from .content_filter import check_fields, contains_filter_words
from .filter_words import BASE_FILTER_WORDS

__all__ = [
    "BASE_FILTER_WORDS",
    "check_fields",
    "contains_filter_words",
]
