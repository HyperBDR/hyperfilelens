from __future__ import annotations

import io
import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.lens_bridge.services.deployment_ai_model import DeploymentAiModelResult


class EnsurePlatformAiModelCommandTests(SimpleTestCase):
    @patch(
        "apps.lens_bridge.management.commands.ensure_platform_ai_model."
        "ensure_platform_ai_model",
        return_value=DeploymentAiModelResult(
            action="updated",
            connectivity_ok=False,
        ),
    )
    def test_reads_secret_from_stdin_without_echoing_it(self, ensure_model):
        secret = "never-print-this-api-key"
        payload = json.dumps(
            {
                "provider": "openai_compatible",
                "model_id": "model/one",
                "display_name": "Model One",
                "api_base": "https://models.example/v1",
                "api_key": secret,
            }
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("sys.stdin", io.StringIO(payload)):
            call_command(
                "ensure_platform_ai_model",
                stdout=stdout,
                stderr=stderr,
            )

        self.assertNotIn(secret, stdout.getvalue())
        self.assertNotIn(secret, stderr.getvalue())
        self.assertIn("updated successfully", stdout.getvalue())
        self.assertIn("HFL_AI_MODEL_STATUS=updated", stdout.getvalue())
        self.assertIn("HFL_AI_MODEL_CONNECTIVITY=failed", stdout.getvalue())
        self.assertIn("core deployment remains healthy", stderr.getvalue())
        passed_config = ensure_model.call_args.args[0]
        self.assertEqual(passed_config.api_key, secret)
