"""Tests for GET /api/v1/auth/captcha-config."""

from django.test import TestCase, override_settings


class CaptchaConfigViewTests(TestCase):
    @override_settings(CAPTCHA_PROVIDER="image")
    def test_image_provider_config(self):
        response = self.client.get("/api/v1/auth/captcha-config")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], "0000")
        self.assertEqual(payload["data"]["captcha_provider"], "image")
        self.assertNotIn("turnstile_site_key", payload["data"])

    @override_settings(
        CAPTCHA_PROVIDER="turnstile",
        TURNSTILE_SITE_KEY="test-site-key",
        TURNSTILE_SECRET_KEY="test-secret-key",
    )
    def test_turnstile_provider_config(self):
        response = self.client.get("/api/v1/auth/captcha-config")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["captcha_provider"], "turnstile")
        self.assertEqual(payload["data"]["turnstile_site_key"], "test-site-key")
        self.assertTrue(payload["data"]["image_fallback_enabled"])

    def test_turnstile_infra_fallback_report_logs_warning(self):
        with self.assertLogs("apps.iam.auth.views.captcha", level="WARNING") as logs:
            response = self.client.post(
                "/api/v1/auth/captcha-fallback-report",
                data={"reason": "widget_error"},
                content_type="application/json",
                HTTP_HOST="app.example.com",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], "0000")
        self.assertTrue(any("[TURNSTILE_FALLBACK]" in msg for msg in logs.output))

    def test_turnstile_infra_fallback_report_rejects_invalid_reason(self):
        response = self.client.post(
            "/api/v1/auth/captcha-fallback-report",
            data={"reason": "user_token_invalid"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_public_captcha_endpoints_ignore_invalid_access_token_cookie(self):
        self.client.cookies["access_token"] = "not-a-valid-jwt"
        for path in (
            "/api/v1/auth/captcha-config",
            "/api/v1/auth/captcha",
            "/api/v1/auth/captcha-fallback-report",
        ):
            with self.subTest(path=path):
                if path.endswith("captcha-config") or path.endswith("/captcha"):
                    response = self.client.get(path)
                else:
                    response = self.client.post(
                        path,
                        data={"reason": "widget_error"},
                        content_type="application/json",
                    )
                self.assertEqual(response.status_code, 200, response.content)
