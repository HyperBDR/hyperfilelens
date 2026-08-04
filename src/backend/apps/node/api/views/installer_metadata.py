"""Publish checksummed metadata for platform-specific minimal installers."""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.node.api import permissions as node_permissions


_EXPECTED_INSTALLERS = {
    "linux-amd64": "tar.gz",
    "linux-arm64": "tar.gz",
    "darwin-amd64": "tar.gz",
    "darwin-arm64": "tar.gz",
    "windows-amd64": "zip",
}


def _manifest_is_materialized(root: Path, payload: object) -> bool:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return False
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(_EXPECTED_INSTALLERS):
        return False
    for key, extension in _EXPECTED_INSTALLERS.items():
        artifact = artifacts.get(key)
        if not isinstance(artifact, dict):
            return False
        filename = artifact.get("filename")
        expected_name = f"hfl-installer-{key}.{extension}"
        if not isinstance(filename, str) or not re.fullmatch(
            rf"[A-Za-z0-9][A-Za-z0-9._-]*/{re.escape(expected_name)}",
            filename,
        ):
            return False
        sha256 = artifact.get("sha256")
        size = artifact.get("size")
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            return False
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            return False
        path = root / filename
        try:
            if not path.is_file() or path.stat().st_size != size:
                return False
        except OSError:
            return False
    return True


class InstallerMetadataView(APIView):
    """Return public file metadata used to build a one-download command."""

    permission_classes = [node_permissions.AllowAny]

    def get(self, _request):
        path = (
            Path(settings.MEDIA_ROOT) / "enroll-bootstrap" / "INSTALLER_MANIFEST.json"
        )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Response(
                {"error": "minimal installer metadata is unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not _manifest_is_materialized(path.parent, payload):
            return Response(
                {"error": "minimal installer metadata is invalid"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        response = Response(payload)
        # Artifact paths are release-versioned, but always fetch the active
        # manifest so newly generated commands target the deployed release.
        response["Cache-Control"] = "no-store"
        return response
