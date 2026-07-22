"""Idempotent deployment ownership for the platform's default AI model."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Mapping
from urllib.parse import urlsplit, urlunsplit

from django.db import DatabaseError, transaction

from apps.lens_bridge.models import LensOrgModelLink
from apps.lens_bridge.services import platform_lens, provisioning, sl_client

DEPLOYMENT_MODEL_MANAGEMENT_KEY = "deployment-default"
logger = logging.getLogger(__name__)


class DeploymentAiModelConfigurationError(ValueError):
    """Raised when deployment input is incomplete or unsafe."""


def _required_single_line(
    values: Mapping[str, Any],
    key: str,
    *,
    max_length: int,
) -> str:
    value = str(values.get(key) or "").strip()
    if not value:
        raise DeploymentAiModelConfigurationError(f"{key} is required")
    if len(value) > max_length or re.search(r"[\x00\r\n]", value):
        raise DeploymentAiModelConfigurationError(
            f"{key} must be a single-line value of at most {max_length} characters"
        )
    return value


def _validated_api_base(values: Mapping[str, Any]) -> str:
    value = _required_single_line(values, "api_base", max_length=2048)
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError as exc:
        raise DeploymentAiModelConfigurationError(
            "api_base must be a valid HTTPS URL"
        ) from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or re.search(r"\s", parsed.netloc)
    ):
        raise DeploymentAiModelConfigurationError(
            "api_base must be an HTTPS URL without credentials, query, or fragment"
        )
    normalized_path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))


@dataclass(frozen=True)
class DeploymentAiModelConfig:
    """Validated deployment input for one OpenAI-compatible model."""

    provider: str
    model_id: str
    display_name: str
    api_base: str
    api_key: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> DeploymentAiModelConfig:
        """Validate and normalize a JSON-compatible configuration mapping."""

        provider = _required_single_line(values, "provider", max_length=64).lower()
        if not re.fullmatch(r"[a-z0-9_]+", provider):
            raise DeploymentAiModelConfigurationError(
                "provider must contain only lowercase letters, numbers, and underscores"
            )
        return cls(
            provider=provider,
            model_id=_required_single_line(values, "model_id", max_length=255),
            display_name=_required_single_line(
                values,
                "display_name",
                max_length=160,
            ),
            api_base=_validated_api_base(values),
            api_key=_required_single_line(values, "api_key", max_length=4096),
        )


@dataclass(frozen=True)
class DeploymentAiModelResult:
    """Sanitized result suitable for management-command output."""

    action: Literal["created", "updated", "recreated"]
    connectivity_ok: bool


def _source_lens_payload(
    config: DeploymentAiModelConfig,
    *,
    make_default: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider": config.provider,
        "config": {
            "model": config.model_id,
            "api_base": config.api_base,
            "api_key": config.api_key,
        },
        "is_active": True,
    }
    if make_default is not None:
        payload["is_default"] = make_default
    return payload


def _source_lens_model(config_uuid: uuid.UUID) -> dict[str, Any] | None:
    try:
        data = sl_client.request_json(
            "GET",
            f"/api/v1/admin/llm-config/{config_uuid}/",
        )
    except sl_client.LensBridgeError as exc:
        if exc.status_code == 404:
            return None
        raise
    if not isinstance(data, dict):
        raise sl_client.LensBridgeError("SourceLens returned an invalid AI model.")
    return data


def _source_lens_model_is_active(config_ref: str) -> bool:
    data = _source_lens_model(uuid.UUID(config_ref))
    if data is None or data.get("is_active") is False:
        return False
    status = str(data.get("status") or "").strip().lower()
    return status not in {"inactive", "disabled"}


def _created_uuid(data: Any) -> uuid.UUID:
    if not isinstance(data, dict) or not data.get("uuid"):
        raise sl_client.LensBridgeError(
            "SourceLens did not return the created AI model identifier."
        )
    try:
        return uuid.UUID(str(data["uuid"]))
    except (TypeError, ValueError) as exc:
        raise sl_client.LensBridgeError(
            "SourceLens returned an invalid AI model identifier."
        ) from exc


@transaction.atomic
def _persist_link(
    *,
    link: LensOrgModelLink | None,
    config_uuid: uuid.UUID,
    display_name: str,
) -> LensOrgModelLink:
    org = platform_lens.get_or_create_platform_org()
    if link is None:
        return LensOrgModelLink.all_objects.create(
            organization=org,
            sl_config_uuid=config_uuid,
            display_name=display_name,
            management_key=DEPLOYMENT_MODEL_MANAGEMENT_KEY,
        )

    link.sl_config_uuid = config_uuid
    link.display_name = display_name
    link.management_key = DEPLOYMENT_MODEL_MANAGEMENT_KEY
    link.is_deleted = False
    link.deleted_at = None
    link.save(
        update_fields=[
            "sl_config_uuid",
            "display_name",
            "management_key",
            "is_deleted",
            "deleted_at",
            "updated_at",
        ]
    )
    return link


def _test_connection(config_uuid: uuid.UUID) -> bool:
    try:
        response = sl_client.request_json(
            "POST",
            f"/api/v1/admin/llm-config/{config_uuid}/test-call/",
            json_body={},
            timeout=90,
        )
    except sl_client.LensBridgeError:
        return False
    if isinstance(response, dict):
        if "ok" in response:
            return bool(response["ok"])
        if "success" in response:
            return bool(response["success"])
    return True


def ensure_platform_ai_model(
    config: DeploymentAiModelConfig,
) -> DeploymentAiModelResult:
    """Create, update, or repair the deployment-owned SourceLens model.

    The first adoption intentionally makes this model the global default. Once
    linked, updates preserve an administrator's later default selection.
    """

    org = platform_lens.get_or_create_platform_org()
    platform_defaults = provisioning.get_or_create_org_link(org)
    link = (
        LensOrgModelLink.all_objects.filter(
            organization=org,
            management_key=DEPLOYMENT_MODEL_MANAGEMENT_KEY,
        )
        .order_by("id")
        .first()
    )
    current = _source_lens_model(link.sl_config_uuid) if link is not None else None
    selected_ref = (
        str(platform_defaults.default_agent_model_ref)
        if platform_defaults.default_agent_model_ref
        else ""
    )
    managed_ref = str(link.sl_config_uuid) if link is not None else ""
    first_adoption = link is None
    should_select_managed = first_adoption or not selected_ref or selected_ref == managed_ref
    if not should_select_managed and not _source_lens_model_is_active(selected_ref):
        should_select_managed = True

    if current is not None and link is not None:
        sl_client.request_json(
            "PUT",
            f"/api/v1/admin/llm-config/{link.sl_config_uuid}/",
            json_body=_source_lens_payload(
                config,
                make_default=True if should_select_managed else None,
            ),
        )
        config_uuid = link.sl_config_uuid
        action: Literal["created", "updated", "recreated"] = "updated"
    else:
        created = sl_client.request_json(
            "POST",
            "/api/v1/admin/llm-config/",
            json_body=_source_lens_payload(
                config,
                make_default=should_select_managed,
            ),
        )
        config_uuid = _created_uuid(created)
        action = "created" if first_adoption else "recreated"

    try:
        _persist_link(
            link=link,
            config_uuid=config_uuid,
            display_name=config.display_name,
        )
    except DatabaseError:
        if action in {"created", "recreated"}:
            try:
                sl_client.request_json(
                    "DELETE",
                    f"/api/v1/admin/llm-config/{config_uuid}/",
                )
            except sl_client.LensBridgeError:
                logger.warning(
                    "Unable to remove orphaned deployment-managed SourceLens model."
                )
        raise
    if should_select_managed and platform_defaults.default_agent_model_ref != config_uuid:
        platform_defaults.default_agent_model_ref = config_uuid
        platform_defaults.save(
            update_fields=["default_agent_model_ref", "updated_at"]
        )
    return DeploymentAiModelResult(
        action=action,
        connectivity_ok=_test_connection(config_uuid),
    )
