"""Tests for optional Cloudflare Turnstile enforcement."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.iam.services.turnstile_verification import (
    missing_turnstile_fields,
    turnstile_configured,
    turnstile_enabled,
    verify_turnstile_for_action,
)


class TurnstileVerificationTests(SimpleTestCase):
    @override_settings(TURNSTILE_ENABLED=False)
    def test_disabled_mode_requires_no_token(self):
        self.assertFalse(turnstile_enabled())
        self.assertEqual(missing_turnstile_fields({}), {})
        self.assertTrue(
            verify_turnstile_for_action({}, MagicMock(), action="login"),
        )

    @override_settings(TURNSTILE_ENABLED=True)
    def test_enabled_mode_requires_token(self):
        self.assertTrue(turnstile_enabled())
        self.assertIn("turnstile_token", missing_turnstile_fields({}))
        self.assertEqual(
            missing_turnstile_fields({"turnstile_token": "tok"}),
            {},
        )

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="site-key",
        TURNSTILE_SECRET_KEY="secret-key",
        FRONTEND_URL="https://app.example.com",
    )
    @patch(
        "apps.iam.services.turnstile_verification.validate_turnstile",
        return_value=True,
    )
    def test_enabled_mode_binds_token_to_action_and_hostname(self, mock_validate):
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}

        self.assertTrue(turnstile_configured())
        self.assertTrue(
            verify_turnstile_for_action(
                {"turnstile_token": "token-value"},
                request,
                action="login",
            ),
        )
        mock_validate.assert_called_once_with(
            "token-value",
            "127.0.0.1",
            expected_action="login",
            expected_hostname="app.example.com",
        )

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="site-key",
        TURNSTILE_SECRET_KEY="",
    )
    def test_enabled_mode_rejects_incomplete_configuration(self):
        self.assertFalse(turnstile_configured())
        self.assertFalse(
            verify_turnstile_for_action(
                {"turnstile_token": "token-value"},
                MagicMock(),
                action="login",
            ),
        )
