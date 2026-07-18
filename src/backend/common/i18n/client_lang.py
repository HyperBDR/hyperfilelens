"""Helpers for activating the best installed language for API requests."""

from django.conf import settings
from django.http import HttpRequest
from django.utils import translation


def activate_request_language(request: HttpRequest) -> None:
    """Activate an installed locale selected from the request headers."""
    supported_languages = dict(settings.LANGUAGES)
    requested_language = translation.get_language_from_request(request)
    if requested_language in supported_languages:
        translation.activate(requested_language)
        return
    translation.activate(settings.LANGUAGE_CODE)
