"""Tests for strict Cloudflare Siteverify response validation."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.iam.services.turnstile_service import validate_turnstile


class TurnstileServiceTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        secret_patcher = patch(
            "apps.platform_ops.services.internal.runtime_settings.turnstile_secret_key",
            return_value="secret-key",
        )
        secret_patcher.start()
        self.addCleanup(secret_patcher.stop)

    def _response(self, *, action: str = "login", hostname: str = "app.example.com"):
        response = MagicMock()
        response.json.return_value = {
            "success": True,
            "action": action,
            "hostname": hostname,
            "error-codes": [],
        }
        return response

    @patch("apps.iam.services.turnstile_service._get_http_session")
    def test_accepts_matching_action_and_hostname(self, mock_session):
        mock_session.return_value.post.return_value = self._response()

        self.assertTrue(
            validate_turnstile(
                "token",
                "203.0.113.10",
                expected_action="login",
                expected_hostname="app.example.com",
            ),
        )

    @patch("apps.iam.services.turnstile_service._get_http_session")
    def test_rejects_action_mismatch(self, mock_session):
        mock_session.return_value.post.return_value = self._response(action="register")

        self.assertFalse(
            validate_turnstile(
                "token",
                expected_action="login",
                expected_hostname="app.example.com",
            ),
        )

    @patch("apps.iam.services.turnstile_service._get_http_session")
    def test_rejects_hostname_mismatch(self, mock_session):
        mock_session.return_value.post.return_value = self._response(
            hostname="other.example.com",
        )

        self.assertFalse(
            validate_turnstile(
                "token",
                expected_action="login",
                expected_hostname="app.example.com",
            ),
        )
