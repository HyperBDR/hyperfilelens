"""Tests for image captcha vs Cloudflare Turnstile verification."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.iam.services.human_verification import (
    get_captcha_provider,
    is_turnstile_mode,
    missing_human_verification_fields,
    verify_human_verification,
)


class HumanVerificationTests(SimpleTestCase):
    @override_settings(CAPTCHA_PROVIDER="image")
    def test_image_mode_requires_id_and_code(self):
        self.assertEqual(get_captcha_provider(), "image")
        self.assertFalse(is_turnstile_mode())
        fields = missing_human_verification_fields({})
        self.assertIn("id", fields)
        self.assertIn("code", fields)

    @override_settings(CAPTCHA_PROVIDER="turnstile")
    def test_turnstile_mode_requires_token(self):
        self.assertTrue(is_turnstile_mode())
        self.assertIn("code", missing_human_verification_fields({}))
        self.assertEqual(missing_human_verification_fields({"turnstile_token": "tok"}), {})

    @override_settings(CAPTCHA_PROVIDER="turnstile")
    @patch("apps.iam.services.human_verification.validate_captcha", return_value=True)
    def test_turnstile_mode_accepts_image_captcha_fallback(self, mock_validate):
        request = MagicMock()
        data = {"id": "captcha_abc", "code": "abcd"}
        self.assertTrue(verify_human_verification(data, request))
        mock_validate.assert_called_once_with("captcha_abc", "abcd")

    @override_settings(CAPTCHA_PROVIDER="image")
    @patch("apps.iam.services.human_verification.validate_captcha", return_value=True)
    def test_image_mode_verify_delegates_to_captcha(self, mock_validate):
        request = MagicMock()
        data = {"id": "captcha_abc", "code": "abcd"}
        self.assertTrue(verify_human_verification(data, request))
        mock_validate.assert_called_once_with("captcha_abc", "abcd")

    @override_settings(CAPTCHA_PROVIDER="turnstile")
    @patch("apps.iam.services.human_verification.validate_turnstile", return_value=True)
    def test_turnstile_mode_verify_delegates_to_turnstile(self, mock_validate):
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        data = {"turnstile_token": "token-value"}
        self.assertTrue(verify_human_verification(data, request))
        mock_validate.assert_called_once_with("token-value", "127.0.0.1")

    @override_settings(CAPTCHA_PROVIDER="turnstile")
    @patch("apps.iam.services.human_verification.validate_turnstile", return_value=False)
    def test_turnstile_mode_verify_rejects_invalid_token(self, _mock_validate):
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        self.assertFalse(verify_human_verification({"turnstile_token": "bad"}, request))
