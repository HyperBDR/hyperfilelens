"""SourceLens MCP server admin helpers."""

from __future__ import annotations

import uuid as uuid_lib
from typing import Any

from rest_framework.exceptions import NotFound

from apps.lens_bridge.services.assistants import _unwrap_list
from apps.lens_bridge.services import sl_client


def list_mcp_servers() -> list[dict[str, Any]]:
    raw = sl_client.request_json("GET", "/api/lens/admin/mcp-servers/")
    return _unwrap_list(raw)


def get_mcp_server(mcp_uuid: uuid_lib.UUID) -> dict[str, Any]:
    data = sl_client.request_json("GET", f"/api/lens/admin/mcp-servers/{mcp_uuid}/")
    if not isinstance(data, dict):
        raise NotFound("MCP server not found.")
    return data


def create_mcp_server(body: dict[str, Any]) -> dict[str, Any]:
    data = sl_client.request_json("POST", "/api/lens/admin/mcp-servers/", json_body=body)
    if not isinstance(data, dict):
        raise sl_client.LensBridgeError("SourceLens MCP server create returned invalid payload.")
    return data


def update_mcp_server(mcp_uuid: uuid_lib.UUID, body: dict[str, Any]) -> dict[str, Any]:
    get_mcp_server(mcp_uuid)
    data = sl_client.request_json(
        "PATCH",
        f"/api/lens/admin/mcp-servers/{mcp_uuid}/",
        json_body=body,
    )
    if not isinstance(data, dict):
        raise sl_client.LensBridgeError("SourceLens MCP server update returned invalid payload.")
    return data


def delete_mcp_server(mcp_uuid: uuid_lib.UUID) -> None:
    get_mcp_server(mcp_uuid)
    sl_client.request_json("DELETE", f"/api/lens/admin/mcp-servers/{mcp_uuid}/")
