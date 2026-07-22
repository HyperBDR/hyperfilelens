"""Platform Ops release and read-only platform APIs."""

from __future__ import annotations

import os
from pathlib import Path

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.node.api.views.bootstrap_templates import (
    BOOTSTRAP_LINUX,
    BOOTSTRAP_MACOS,
    BOOTSTRAP_WINDOWS,
    bootstrap_dir,
)
from apps.node.services.internal.agent_release import (
    agent_releases_root,
    latest_published_agent_version,
    semver_sort_key,
)
from django.db.models import Count, Q

from apps.alert.api.serializers import AlertPolicySerializer
from apps.alert.models import AlertPolicy
from apps.lens_bridge import deploy as lens_deploy
from apps.lens_bridge.services import sl_client
from apps.notification.models import NotificationChannel
from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.views._utils import paginated, safe_int

_BOOTSTRAP_FILES = frozenset(
    {
        BOOTSTRAP_LINUX,
        BOOTSTRAP_MACOS,
        BOOTSTRAP_WINDOWS,
    },
)
_ENROLL_SCRIPT_FILES = frozenset({"enroll-linux.sh", "enroll-windows.ps1"})
_KIND_ORDER = {"binary": 0, "bootstrap": 1, "enroll": 2, "other": 3}


def _artifact_kind(name: str) -> str:
    if name in _BOOTSTRAP_FILES:
        return "bootstrap"
    if name in _ENROLL_SCRIPT_FILES or name.startswith("hfl-enroll-"):
        return "enroll"
    if name.startswith("hfl-agent-") and (
        name.endswith(".tar.gz") or name.endswith(".zip")
    ):
        return "binary"
    return "other"


def _artifact_sort_key(row: dict) -> tuple:
    version = semver_sort_key(str(row.get("version") or ""))
    kind = _KIND_ORDER.get(str(row.get("kind") or ""), 9)
    return (-version[0], -version[1], -version[2], kind, str(row.get("name") or ""))


def _list_agent_release_artifacts(root: Path) -> list[dict]:
    rows: list[dict] = []
    if not root.is_dir():
        return rows
    for child in sorted(root.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        version = child.name
        for file in sorted(child.iterdir()):
            if not file.is_file():
                continue
            name = file.name
            rows.append(
                {
                    "version": version,
                    "name": name,
                    "kind": _artifact_kind(name),
                    "size_bytes": file.stat().st_size,
                }
            )
    rows.sort(key=_artifact_sort_key)
    return rows


def _bootstrap_runtime_info() -> dict[str, str]:
    version = latest_published_agent_version()
    releases_dir = agent_releases_root() / version
    fallback_dir = bootstrap_dir()
    published = (releases_dir / BOOTSTRAP_LINUX).is_file()
    if published:
        return {
            "active_source": "published",
            "active_path": str(releases_dir),
            "fallback_path": str(fallback_dir),
            "version": version,
        }
    return {
        "active_source": "fallback",
        "active_path": str(fallback_dir),
        "fallback_path": str(fallback_dir),
        "version": version,
    }


class PlatformOpsPlatformAgentReleasesView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        root = agent_releases_root()
        pinned = os.getenv("AGENT_VERSION", "").strip() or None
        latest = latest_published_agent_version()
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20, max_value=200)
        artifacts = _list_agent_release_artifacts(root)
        total = len(artifacts)
        offset = (page - 1) * page_size
        page_rows = artifacts[offset : offset + page_size]
        payload = paginated(page_rows, total=total, page=page, page_size=page_size)
        payload.update(
            {
                "pinned_version": pinned,
                "latest_version": latest,
                "root": str(root),
                "bootstrap": _bootstrap_runtime_info(),
            }
        )
        return Response(payload)


class PlatformOpsPlatformNotificationChannelsView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20, max_value=200)
        qs = (
            NotificationChannel.objects.select_related("organization")
            .annotate(delivery_count=Count("deliveries"))
            .order_by("organization__key", "name", "id")
        )
        search = str(request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(channel_type__icontains=search)
                | Q(organization__key__icontains=search)
                | Q(organization__name__icontains=search)
            )
        channel_type = str(request.query_params.get("type") or "").strip()
        if channel_type:
            qs = qs.filter(channel_type=channel_type)
        active = str(request.query_params.get("active") or "").strip().lower()
        if active in {"true", "false"}:
            qs = qs.filter(is_active=active == "true")
        org_key = str(request.query_params.get("org") or "").strip()
        if org_key:
            qs = qs.filter(organization__key=org_key)
        total = qs.count()
        all_channels = NotificationChannel.objects.all()
        stats = {
            "total": all_channels.count(),
            "active": all_channels.filter(is_active=True).count(),
            "inactive": all_channels.filter(is_active=False).count(),
            "types": all_channels.values("channel_type").distinct().count(),
        }
        offset = (page - 1) * page_size
        rows = []
        for channel in qs[offset : offset + page_size]:
            rows.append(
                {
                    "id": channel.id,
                    "organization_id": channel.organization_id,
                    "organization_key": channel.organization.key,
                    "organization_name": channel.organization.name,
                    "name": channel.name,
                    "channel_type": channel.channel_type,
                    "is_active": channel.is_active,
                    "delivery_count": channel.delivery_count,
                    "updated_at": channel.updated_at,
                }
            )
        return Response(
            paginated(
                rows,
                total=total,
                page=page,
                page_size=page_size,
                extra={"stats": stats},
            )
        )


class PlatformOpsPlatformIntegrationsView(APIView):
    """Deployment-managed service integrations visible to platform operators."""

    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        health = sl_client.ping(timeout=3)
        return Response(
            {
                "integrations": [
                    {
                        "key": "sourcelens",
                        "name": "SourceLens",
                        "category": "AI and data services",
                        "mode": lens_deploy.sourcelens_mode(),
                        "base_url": lens_deploy.lens_base_url(),
                        "gateway_base_url": lens_deploy.lens_gateway_base_url(),
                        "configured": bool(health.get("configured")),
                        "reachable": bool(health.get("reachable")),
                        "authenticated": bool(health.get("authenticated")),
                        "managed_by": "deployment",
                    }
                ]
            }
        )


class PlatformOpsPlatformAlertPoliciesView(APIView):
    """Cross-account alert policy inventory for the Admin Console."""

    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20, max_value=200)
        qs = AlertPolicy.objects.select_related("organization").order_by(
            "organization__key",
            "name",
            "id",
        )
        search = str(request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(organization__key__icontains=search)
                | Q(organization__name__icontains=search)
            )
        for field in ("type", "severity"):
            value = str(request.query_params.get(field) or "").strip()
            if value:
                qs = qs.filter(**{field: value})
        enabled = str(request.query_params.get("enabled") or "").strip().lower()
        if enabled in {"true", "false"}:
            qs = qs.filter(enabled=enabled == "true")
        org_key = str(request.query_params.get("org") or "").strip()
        if org_key:
            qs = qs.filter(organization__key=org_key)

        total = qs.count()
        all_qs = AlertPolicy.objects.all()
        stats = {
            "total": all_qs.count(),
            "enabled": all_qs.filter(enabled=True).count(),
            "disabled": all_qs.filter(enabled=False).count(),
            "critical": all_qs.filter(severity="critical").count(),
        }
        offset = (page - 1) * page_size
        rows = []
        for policy in qs[offset : offset + page_size]:
            row = AlertPolicySerializer(policy).data
            row["organization_key"] = policy.organization.key
            row["organization_name"] = policy.organization.name
            rows.append(row)
        return Response(
            paginated(
                rows,
                total=total,
                page=page,
                page_size=page_size,
                extra={"stats": stats},
            )
        )
