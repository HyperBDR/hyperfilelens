"""SourceLens bridge credentials and base URL (env-only)."""

from __future__ import annotations

from project.settings.env import env_str

# Public HTTPS path used by bundled SourceLens Data Gateways.
LENS_GATEWAY_PUBLIC_PATH = "/sourcelens"


def lens_base_url() -> str:
    return env_str("LENS_BASE_URL", "").rstrip("/")


def sourcelens_mode() -> str:
    mode = env_str("SOURCELENS_MODE", "bundled").strip().lower()
    return mode if mode in {"bundled", "external"} else "bundled"


def lens_gateway_base_url() -> str:
    """SourceLens URL reachable from enrolled gateway hosts (native OS, not Docker DNS)."""
    explicit = env_str("LENS_GATEWAY_BASE_URL", "").rstrip("/")
    if explicit:
        return explicit

    base = lens_base_url()
    if sourcelens_mode() == "external":
        return base

    frontend = env_str("FRONTEND_URL", "").rstrip("/")
    if frontend:
        return f"{frontend}{LENS_GATEWAY_PUBLIC_PATH}"

    if not base:
        return ""
    # host.docker.internal resolves inside Docker only; gateway install runs on the host OS.
    if "host.docker.internal" in base:
        return base.replace("host.docker.internal", "127.0.0.1")
    return base


def lens_bridge_username() -> str:
    """SL service account login username."""
    return env_str("LENS_BRIDGE_USERNAME", "")


def lens_bridge_password() -> str:
    return env_str("LENS_BRIDGE_PASSWORD", "")


def lens_bridge_configured() -> bool:
    return bool(lens_base_url() and lens_bridge_username() and lens_bridge_password())
