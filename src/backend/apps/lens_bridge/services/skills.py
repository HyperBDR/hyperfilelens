"""SourceLens skill admin helpers."""

from __future__ import annotations

import uuid as uuid_lib
from typing import Any

from rest_framework.exceptions import NotFound

from apps.lens_bridge.services.assistants import _unwrap_list
from apps.lens_bridge.services import sl_client


def list_skills() -> list[dict[str, Any]]:
    raw = sl_client.request_json("GET", "/api/lens/admin/skills/")
    return _unwrap_list(raw)


def get_skill(skill_uuid: uuid_lib.UUID) -> dict[str, Any]:
    data = sl_client.request_json("GET", f"/api/lens/admin/skills/{skill_uuid}/")
    if not isinstance(data, dict):
        raise NotFound("Skill not found.")
    return data


def create_skill(body: dict[str, Any]) -> dict[str, Any]:
    data = sl_client.request_json("POST", "/api/lens/admin/skills/", json_body=body)
    if not isinstance(data, dict):
        raise sl_client.LensBridgeError("SourceLens skill create returned invalid payload.")
    return data


def update_skill(skill_uuid: uuid_lib.UUID, body: dict[str, Any]) -> dict[str, Any]:
    get_skill(skill_uuid)
    data = sl_client.request_json(
        "PATCH",
        f"/api/lens/admin/skills/{skill_uuid}/",
        json_body=body,
    )
    if not isinstance(data, dict):
        raise sl_client.LensBridgeError("SourceLens skill update returned invalid payload.")
    return data


def delete_skill(skill_uuid: uuid_lib.UUID) -> None:
    get_skill(skill_uuid)
    sl_client.request_json("DELETE", f"/api/lens/admin/skills/{skill_uuid}/")


def beautify_skill(body: dict[str, Any]) -> dict[str, Any]:
    data = sl_client.request_json(
        "POST",
        "/api/lens/admin/skills/beautify/",
        json_body=body,
    )
    if not isinstance(data, dict):
        raise sl_client.LensBridgeError("SourceLens skill beautify returned invalid payload.")
    return data
