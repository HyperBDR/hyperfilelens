"""Language-related middleware."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils import translation


class LanguageCodeMappingMiddleware:
    """Map browser language tags to Django codes and activate translations.

    Uses ``LANGUAGE_CODE_MAPPING`` from settings to map browser language
    variants (e.g. ``fr-ca``) to Django codes (e.g. ``fr``).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.language_mapping = getattr(settings, "LANGUAGE_CODE_MAPPING", {})
        self._supported_languages = dict(settings.LANGUAGES)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        accept_language = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        activated = False
        if accept_language:
            parts = accept_language.split(",")
            first_part = parts[0].strip()
            first_lang = first_part.split(";")[0].strip().lower()

            mapped_lang = self.language_mapping.get(first_lang)
            if mapped_lang and mapped_lang in self._supported_languages:
                quality_part = first_part.split(";", 1)
                if len(quality_part) > 1:
                    new_first_part = f"{mapped_lang};{quality_part[1]}"
                else:
                    new_first_part = mapped_lang

                remaining = ",".join(parts[1:]) if len(parts) > 1 else ""
                new_accept_language = f"{new_first_part},{remaining}".rstrip(",")
                request.META["HTTP_ACCEPT_LANGUAGE"] = new_accept_language
                translation.activate(mapped_lang)
                activated = True
            elif first_lang in self._supported_languages:
                translation.activate(first_lang)
                activated = True

        if not activated:
            translation.activate(settings.LANGUAGE_CODE)

        return self.get_response(request)
