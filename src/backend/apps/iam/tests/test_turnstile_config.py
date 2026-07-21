"""Tests for GET /api/v1/auth/turnstile/config."""

from django.test import TestCase, override_settings


class TurnstileConfigViewTests(TestCase):
    @override_settings(TURNSTILE_ENABLED=False)
    def test_disabled_config(self):
        response = self.client.get("/api/v1/auth/turnstile/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], "0000")
        self.assertFalse(payload["data"]["enabled"])
        self.assertFalse(payload["data"]["configured"])
        self.assertNotIn("site_key", payload["data"])

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="test-secret-key",
    )
    def test_enabled_config(self):
        response = self.client.get("/api/v1/auth/turnstile/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["data"]["enabled"])
        self.assertTrue(payload["data"]["configured"])
        self.assertEqual(payload["data"]["site_key"], "test-site-key")

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="",
    )
    def test_incomplete_config_fails_closed(self):
        response = self.client.get("/api/v1/auth/turnstile/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["data"]["enabled"])
        self.assertFalse(payload["data"]["configured"])
        self.assertNotIn("site_key", payload["data"])

    def test_public_config_ignores_invalid_access_token_cookie(self):
        self.client.cookies["access_token"] = "not-a-valid-jwt"
        response = self.client.get("/api/v1/auth/turnstile/config")

        self.assertEqual(response.status_code, 200, response.content)

    def test_legacy_image_captcha_endpoints_are_removed(self):
        for path in (
            "/api/v1/auth/captcha-config",
            "/api/v1/auth/captcha",
            "/api/v1/auth/captcha/validate",
            "/api/v1/auth/captcha-fallback-report",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
