"""Create or update the deployment-managed platform AI model."""

from __future__ import annotations

import json
import sys
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from apps.lens_bridge.services import sl_client
from apps.lens_bridge.services.deployment_ai_model import (
    DeploymentAiModelConfig,
    DeploymentAiModelConfigurationError,
    ensure_platform_ai_model,
)

MAX_INPUT_BYTES = 16 * 1024


class Command(BaseCommand):
    """Apply one complete AI model configuration supplied through stdin."""

    help = "Create or update the deployment-managed platform AI model from JSON stdin."

    def handle(self, *args: Any, **options: Any) -> None:
        raw = sys.stdin.read(MAX_INPUT_BYTES + 1)
        if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
            raise CommandError("AI model configuration exceeds the allowed size.")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandError("AI model configuration must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise CommandError("AI model configuration must be a JSON object.")

        try:
            config = DeploymentAiModelConfig.from_mapping(payload)
            result = ensure_platform_ai_model(config)
        except DeploymentAiModelConfigurationError as exc:
            raise CommandError(str(exc)) from exc
        except sl_client.LensBridgeError as exc:
            raise CommandError(
                "Unable to apply the deployment-managed AI model in SourceLens."
            ) from exc
        except DatabaseError as exc:
            raise CommandError(
                "Unable to persist the deployment-managed AI model link."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Deployment-managed AI model {result.action} successfully."
            )
        )
        self.stdout.write(f"HFL_AI_MODEL_STATUS={result.action}")
        if not result.connectivity_ok:
            self.stdout.write("HFL_AI_MODEL_CONNECTIVITY=failed")
            self.stderr.write(
                self.style.WARNING(
                    "AI model connectivity test failed; core deployment remains healthy."
                )
            )
        else:
            self.stdout.write("HFL_AI_MODEL_CONNECTIVITY=passed")
