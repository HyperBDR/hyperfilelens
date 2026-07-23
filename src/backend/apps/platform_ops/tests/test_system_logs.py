from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.platform_ops.api.views.system import _read_log_rows, _redact_log_message


class PlatformSystemLogTests(SimpleTestCase):
    def test_sensitive_values_are_redacted(self):
        message = (
            "authorization: Bearer live-token password=secret "
            "api_key=provider-key"
        )

        redacted = _redact_log_message(message)

        self.assertNotIn("live-token", redacted)
        self.assertNotIn("secret", redacted)
        self.assertNotIn("provider-key", redacted)
        self.assertIn("authorization: [REDACTED]", redacted)

    def test_nested_json_secrets_are_redacted(self):
        message = (
            '{"request":{"api_key":"provider-key","safe":"visible"},'
            '"Authorization":"Bearer live-token","items":[{"password":"secret"}]}'
        )

        redacted = _redact_log_message(message)

        self.assertNotIn("provider-key", redacted)
        self.assertNotIn("live-token", redacted)
        self.assertNotIn("secret", redacted)
        self.assertIn('"safe":"visible"', redacted)
        self.assertEqual(redacted.count("[REDACTED]"), 3)

    def test_embedded_json_style_secret_is_redacted(self):
        redacted = _redact_log_message(
            'request payload={"turnstile_secret_key":"provider-key",'
            '"accessToken":"live-token"} status=failed'
        )

        self.assertNotIn("provider-key", redacted)
        self.assertNotIn("live-token", redacted)
        self.assertIn('"turnstile_secret_key":[REDACTED]', redacted)
        self.assertIn('"accessToken":[REDACTED]', redacted)

    def test_reads_and_orders_recent_log_rows(self):
        with TemporaryDirectory() as root:
            log_path = Path(root) / "api.log"
            log_path.write_text(
                "[2026-07-22T10:00:00Z] [INFO] started\n"
                "[2026-07-22T10:01:00Z] [ERROR] token=private failed\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"HFL_LOG_DIR": root}):
                rows = _read_log_rows()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["level"], "ERROR")
        self.assertEqual(rows[0]["service"], "api")
        self.assertNotIn("private", rows[0]["message"])
        self.assertEqual(rows[1]["timestamp"], "2026-07-22T10:00:00Z")
