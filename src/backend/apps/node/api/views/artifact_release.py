"""Agent binary release URLs and Nginx agent-releases auth."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, urlparse, urlsplit, urlunsplit

from django.core import signing
from django.core.signing import BadSignature, SignatureExpired
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.models import Organization
from apps.iam.permissions_org import resolve_org_key
from apps.node.api import permissions as node_permissions
from apps.node.api.views.enrollment_helpers import (
    get_valid_enrollment_token,
    token_usable_for_artifact_download,
)
from apps.node.models import Node
from apps.node.services.internal.agent_release import (
    AGENT_RELEASES_URL_PREFIX,
    agent_releases_root,
    dist_filename,
    latest_published_agent_version,
    normalize_ubuntu_bundle_release,
    resolve_agent_version,
    ubuntu_bundle_release,
    version_has_dist,
)

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None


@dataclass(frozen=True)
class AgentArtifact:
    platform: str
    arch: str
    version: str
    filename: str

    @property
    def artifact_path(self) -> str:
        return f"{AGENT_RELEASES_URL_PREFIX}/{self.version}/{self.filename}"


def _normalize_platform(value: str | None) -> str | None:
    if not value:
        return None
    platform = str(value).strip().lower()
    if platform in ("linux", "darwin", "windows"):
        return platform
    return None


def _normalize_arch(value: str | None) -> str | None:
    if not value:
        return None
    arch = str(value).strip().lower()
    if arch in ("x86_64", "amd64", "x64"):
        return "amd64"
    if arch in ("aarch64", "arm64"):
        return "arm64"
    return None


def _get_agent_artifact(
    role: str,
    *,
    platform: str | None = None,
    arch: str | None = None,
    os_version: str | None = None,
) -> AgentArtifact:
    plat = _normalize_platform(platform) or os.getenv("AGENT_PLATFORM", "linux")
    machine = _normalize_arch(arch) or os.getenv("AGENT_ARCH", "amd64")
    version = resolve_agent_version(plat, machine, role, os_version)
    ubuntu_release = ubuntu_bundle_release(role, plat, os_version)
    filename = os.getenv("AGENT_FILENAME") or dist_filename(
        version,
        plat,
        machine,
        ubuntu_release=ubuntu_release,
    )
    return AgentArtifact(platform=plat, arch=machine, version=version, filename=filename)


def _build_download_url(request, artifact: AgentArtifact, signed: str) -> str:
    """Prefer client ``api_base`` (console origin) over internal request host."""
    api_base = str(request.query_params.get("api_base") or "").strip().rstrip("/")
    if api_base:
        return f"{api_base}{artifact.artifact_path}?t={quote(signed, safe='')}"

    forwarded_proto = str(request.headers.get("X-Forwarded-Proto") or "").strip()
    forwarded_host = str(request.headers.get("X-Forwarded-Host") or "").strip()
    if forwarded_proto and forwarded_host:
        parts = urlsplit(request.build_absolute_uri(artifact.artifact_path))
        return urlunsplit(
            (
                forwarded_proto,
                forwarded_host,
                parts.path,
                f"t={quote(signed, safe='')}",
                "",
            ),
        )

    download_url = request.build_absolute_uri(artifact.artifact_path)
    sep = "&" if "?" in download_url else "?"
    return f"{download_url}{sep}t={quote(signed, safe='')}"


def _make_release_token(payload: dict, ttl_seconds: int) -> str:
    return signing.dumps(payload, salt="agent-releases", compress=True) + f".ttl{ttl_seconds}"


def _load_release_token(token: str, max_age: int) -> dict | None:
    token = (token or "").split(".ttl", 1)[0]
    try:
        return signing.loads(token, salt="agent-releases", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def _release_download_token(request) -> str:
    """Read signed ``t`` from query or from ``X-Original-URI`` (nginx auth_request)."""
    direct = str(request.query_params.get("t") or "").strip()
    if direct:
        return direct
    original_uri = str(request.headers.get("X-Original-URI", "") or "").strip()
    if "?" not in original_uri:
        return ""
    parsed = urlparse(original_uri)
    values = parse_qs(parsed.query).get("t") or []
    return str(values[0]).strip() if values else ""


def _release_file_exists(release_path: str) -> bool:
    prefix = f"{AGENT_RELEASES_URL_PREFIX}/"
    if not release_path.startswith(prefix):
        return False
    rel = release_path.removeprefix(prefix)
    return (agent_releases_root() / rel).is_file()


def _redis_client():
    if redis is None:
        return None
    url = os.getenv("AGENT_RELEASES_REDIS_URL") or os.getenv("CACHE_REDIS_URL") or os.getenv(
        "CELERY_BROKER_URL",
        "redis://redis:6379/0",
    )
    try:
        return redis.Redis.from_url(url, decode_responses=True)
    except OSError:
        return None


_SLOT_LUA = """
local key = KEYS[1]
local token = ARGV[1]
local maxn = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

if redis.call('SISMEMBER', key, token) == 1 then
  return {1, redis.call('SCARD', key)}
end

local added = redis.call('SADD', key, token)
local n = redis.call('SCARD', key)
redis.call('EXPIRE', key, ttl)

if n > maxn then
  if added == 1 then
    redis.call('SREM', key, token)
  end
  return {0, n}
end
return {1, n}
"""


def _try_acquire_slot(tenant_key: str, slot_id: str) -> tuple[bool, int]:
    maxn = int(os.getenv("AGENT_RELEASES_TENANT_MAX_CONCURRENT_DOWNLOADS", "20"))
    ttl = int(os.getenv("AGENT_RELEASES_SLOT_TTL_SECONDS", "3600"))
    client = _redis_client()
    if client is None:
        return True, 0
    key = f"hfl:agent-releases:slots:{tenant_key}"
    try:
        allowed, count = client.eval(_SLOT_LUA, 1, key, slot_id, str(maxn), str(ttl))
        return bool(int(allowed)), int(count)
    except (OSError, TypeError, ValueError):
        return True, 0


class AgentLatestReleaseView(APIView):
    """Published agent semver for console upgrade UI."""

    permission_classes = [
        node_permissions.IsAuthenticated,
        node_permissions.IsOrgStaffReader,
    ]

    def get(self, request):
        return Response({"version": latest_published_agent_version()})


class AgentReleaseView(APIView):
    """Issue a short-lived signed download URL for the agent binary."""

    permission_classes = [node_permissions.AllowAny]

    def get(self, request):
        org_key = str(request.query_params.get("org") or "").strip()
        role = str(request.query_params.get("role") or "").strip()
        enroll_token = str(request.query_params.get("token") or "").strip()
        plat_raw = str(request.query_params.get("platform") or "").strip()
        arch_raw = str(request.query_params.get("arch") or "").strip()
        os_version = str(request.query_params.get("os_version") or "").strip()

        platform: str | None = None
        if plat_raw:
            platform = _normalize_platform(plat_raw)
            if platform is None:
                return Response({"error": "invalid platform"}, status=400)

        arch: str | None = None
        if arch_raw:
            arch = _normalize_arch(arch_raw)
            if arch is None:
                return Response({"error": "invalid arch"}, status=400)

        if (
            platform == "linux"
            and role in {Node.Role.PROXY, Node.Role.GATEWAY}
            and os_version
            and normalize_ubuntu_bundle_release(os_version) is None
        ):
            return Response(
                {"error": "gateway/proxy supports Ubuntu 20.04 or 24.04"},
                status=400,
            )

        if not org_key or role not in dict(Node.Role.choices) or not enroll_token:
            return Response({"error": "org/role/token required"}, status=400)

        org = Organization.objects.filter(key=org_key, is_active=True).first()
        if org is None:
            return Response({"error": "organization not found"}, status=404)

        if get_valid_enrollment_token(org=org, token=enroll_token, role=role) is None:
            if not token_usable_for_artifact_download(
                org=org,
                token=enroll_token,
                role=role,
            ):
                return Response({"error": "invalid enrollment token"}, status=401)

        artifact = _get_agent_artifact(
            role,
            platform=platform,
            arch=arch,
            os_version=os_version,
        )
        ttl = int(os.getenv("AGENT_RELEASE_URL_TTL_SECONDS", "600"))
        signed = _make_release_token(
            {
                "p": artifact.artifact_path,
                "org": org.key,
                "role": role,
                "enroll": enroll_token,
            },
            ttl_seconds=ttl,
        )

        download_url = _build_download_url(request, artifact, signed)

        return Response(
            {
                "version": artifact.version,
                "platform": artifact.platform,
                "arch": artifact.arch,
                "path": artifact.artifact_path,
                "download_url": download_url,
                "expires_in": ttl,
            }
        )


class AgentReleasesAuthView(APIView):
    """Nginx ``auth_request`` hook for ``/media/agent-releases/*`` downloads."""

    permission_classes = [node_permissions.AllowAny]

    def get(self, request):
        original_uri = str(request.headers.get("X-Original-URI", "") or "").strip()
        token = _release_download_token(request)
        ttl = int(os.getenv("AGENT_RELEASE_URL_TTL_SECONDS", "600"))

        payload = _load_release_token(token, max_age=ttl)
        if not payload:
            return Response(
                {"error": "invalid token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        expected_path = str(payload.get("p") or "")
        org_key = str(payload.get("org") or "")
        enroll = str(payload.get("enroll") or "")
        role = str(payload.get("role") or "")
        releases_prefix = f"{AGENT_RELEASES_URL_PREFIX}/"
        if not expected_path.startswith(releases_prefix):
            return Response(
                {"error": "invalid path"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        req_path = original_uri.split("?", 1)[0] if original_uri else ""
        if req_path != expected_path:
            if req_path.startswith(releases_prefix):
                return Response(
                    {"error": "path mismatch"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if not _release_file_exists(expected_path):
                return Response(
                    {"error": "release not found"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        header_org = resolve_org_key(request)
        if header_org and header_org != org_key:
            return Response(
                {"error": "org mismatch"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        org = Organization.objects.filter(key=org_key, is_active=True).first()
        if org is None:
            return Response(
                {"error": "organization not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if get_valid_enrollment_token(org=org, token=enroll, role=role) is None:
            if not token_usable_for_artifact_download(org=org, token=enroll, role=role):
                return Response(
                    {"error": "invalid enrollment token"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        ok, _count = _try_acquire_slot(org.key, enroll or token)
        if not ok:
            # Nginx auth_request treats only 401/403 as expected denials; 429 becomes 500.
            return Response(
                {"error": "too many concurrent downloads"},
                status=status.HTTP_403_FORBIDDEN,
            )

        resp = Response(status=status.HTTP_204_NO_CONTENT)
        resp["X-Tenant-Key"] = org.key
        return resp


# Backward-compatible aliases for tests and internal imports.
_agent_releases_root = agent_releases_root
_resolve_agent_version = resolve_agent_version
_version_has_dist = version_has_dist
_dist_filename = dist_filename
_ubuntu_bundle_release = ubuntu_bundle_release
