#!/usr/bin/env python3
"""Map HFL runtime Sentry settings into the bundled SourceLens stack."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shlex
import tempfile
from urllib.parse import urlsplit

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_SAMPLE_RATE = re.compile(r"0(?:\.\d+)?|1(?:\.0+)?")


def read_env(path: pathlib.Path) -> dict[str, str]:
    """Read the Compose-compatible subset used by HFL runtime files."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value[:1] in {"'", '"'}:
            try:
                decoded = shlex.split(value)
            except ValueError:
                decoded = []
            value = decoded[0] if len(decoded) == 1 else ""
        values[key.strip()] = value.replace("$$", "$")
    return values


def valid_dsn(value: str) -> bool:
    """Return whether *value* is a structurally valid Sentry DSN."""
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError:
        return False
    project_id = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and parsed.username
        and project_id.isdigit()
        and not parsed.query
        and not parsed.fragment
        and not re.search(r"[\x00\r\n\s]", value)
    )


def valid_frontend_dsn(value: str) -> bool:
    """Return whether a DSN contains only browser-public credentials."""
    if not valid_dsn(value):
        return False
    return urlsplit(value).password is None


def set_key(text: str, name: str, value: str) -> str:
    """Set one Compose environment key with literal-value escaping."""
    safe = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
    rendered = f'{name}="{safe}"' if value else f"{name}="
    pattern = rf"^{re.escape(name)}=.*$"
    if re.search(pattern, text, flags=re.M):
        return re.sub(pattern, rendered, text, count=1, flags=re.M)
    return text.rstrip() + f"\n{rendered}\n"


def atomic_write(path: pathlib.Path, text: str, mode: int) -> None:
    """Write text through a same-directory temporary file with fixed permissions."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        path.chmod(mode)
    finally:
        if temporary.exists():
            temporary.unlink()


def sync_configuration(
    parent_path: pathlib.Path,
    env_path: pathlib.Path,
    build_info_path: pathlib.Path,
    output_path: pathlib.Path,
) -> None:
    """Synchronize backend settings and generate the browser runtime payload."""
    parent = read_env(parent_path)
    build_info = json.loads(build_info_path.read_text(encoding="utf-8"))
    enabled = parent.get("SENTRY_ENABLED", "").lower() in _TRUTHY
    backend_dsn = parent.get("SENTRY_BACKEND_DSN", "") if enabled else ""
    frontend_dsn = parent.get("SENTRY_FRONTEND_DSN", "") if enabled else ""
    environment = parent.get("SENTRY_ENVIRONMENT", "") if enabled else ""
    traces = parent.get("SENTRY_TRACES_SAMPLE_RATE", "0") if enabled else "0"
    if not valid_dsn(backend_dsn):
        backend_dsn = ""
    if not valid_frontend_dsn(frontend_dsn):
        frontend_dsn = ""
    enabled = enabled and bool(backend_dsn or frontend_dsn) and bool(environment)

    hfl_version = parent.get("APP_VERSION", "unknown")
    sl_version = str(build_info.get("version") or "unknown")
    backend_release = f"hyperfilelens-sourcelens@{hfl_version}-sl{sl_version}"
    frontend_release = f"hyperfilelens-sourcelens-frontend@{hfl_version}-sl{sl_version}"
    lensnode_release = f"hyperfilelens-lensnode@{hfl_version}-sl{sl_version}"

    text = env_path.read_text(encoding="utf-8")
    for key, value in {
        "SENTRY_ENABLED": "true" if enabled else "false",
        "SENTRY_DSN": backend_dsn,
        "SENTRY_FRONTEND_DSN": frontend_dsn,
        "SENTRY_ENVIRONMENT": environment,
        "SENTRY_RELEASE": backend_release,
        "SENTRY_FRONTEND_RELEASE": frontend_release,
        "SENTRY_LENSNODE_RELEASE": lensnode_release,
        "SENTRY_TRACES_SAMPLE_RATE": traces if _SAMPLE_RATE.fullmatch(traces) else "0",
        "SENTRY_PROFILING_SAMPLE_RATE": "0",
        "SENTRY_SEND_DEFAULT_PII": "false",
    }.items():
        text = set_key(text, key, value)
    atomic_write(env_path, text, 0o600)

    payload = {
        "enabled": bool(enabled and frontend_dsn),
        "dsn": frontend_dsn,
        "environment": environment,
        "release": frontend_release,
        "tracesSampleRate": float(traces) if _SAMPLE_RATE.fullmatch(traces) else 0,
    }
    atomic_write(
        output_path,
        "window.__HFL_SOURCELENS_SENTRY__ = Object.freeze("
        + json.dumps(payload, separators=(",", ":"))
        + ")\n",
        0o644,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-env", required=True, type=pathlib.Path)
    parser.add_argument("--sourcelens-env", required=True, type=pathlib.Path)
    parser.add_argument("--build-info", required=True, type=pathlib.Path)
    parser.add_argument("--frontend-config", required=True, type=pathlib.Path)
    arguments = parser.parse_args()
    sync_configuration(
        arguments.parent_env,
        arguments.sourcelens_env,
        arguments.build_info,
        arguments.frontend_config,
    )


if __name__ == "__main__":
    main()
