"""Validate the configured Google OAuth entry point without contacting Google."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit, urlunsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings
from django.urls import reverse

from apps.configuration.services.runtime_settings import (
    google_oauth_enabled,
    google_oauth_ready,
)
from common.deploy.site import tenant_public_url


class Command(BaseCommand):
    """Check the local OAuth route and its canonical Google callback."""

    help = "Validate Google OAuth readiness without external connectivity."

    def handle(self, *args: Any, **options: Any) -> None:
        if not google_oauth_enabled():
            self.stdout.write("HFL_GOOGLE_OAUTH_STATUS=disabled")
            return
        if not google_oauth_ready():
            raise CommandError(
                "Google OAuth is enabled but a unique site-bound application is unavailable."
            )

        public_url = tenant_public_url()
        parsed_public = urlsplit(public_url)
        if parsed_public.scheme not in {"http", "https"} or not parsed_public.hostname:
            raise CommandError("FRONTEND_URL must be an absolute HTTP(S) URL.")

        allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
        if parsed_public.hostname not in allowed_hosts:
            allowed_hosts.append(parsed_public.hostname)
        with override_settings(ALLOWED_HOSTS=allowed_hosts):
            response = Client().get(
                reverse("google_login"),
                secure=parsed_public.scheme == "https",
                HTTP_HOST=parsed_public.netloc,
                HTTP_X_FORWARDED_PROTO=parsed_public.scheme,
                HTTP_X_HFL_SITE_ROLE="tenant",
            )

        if response.status_code != 302:
            raise CommandError(
                "Google OAuth login did not return the expected HTTP 302 redirect."
            )
        location = str(response.headers.get("Location") or "")
        parsed_location = urlsplit(location)
        if parsed_location.scheme != "https" or parsed_location.hostname != "accounts.google.com":
            raise CommandError("Google OAuth login did not redirect to accounts.google.com.")

        callback = parse_qs(parsed_location.query).get("redirect_uri", [""])[0]
        expected_callback = urlunsplit(
            (
                parsed_public.scheme,
                parsed_public.netloc,
                "/accounts/google/login/callback/",
                "",
                "",
            )
        )
        if callback != expected_callback:
            raise CommandError("Google OAuth generated an unexpected callback URI.")

        self.stdout.write(f"Google OAuth callback: {expected_callback}")
        self.stdout.write("HFL_GOOGLE_OAUTH_STATUS=ready")
