#!/usr/bin/env python3
"""Apply deployment-specific public URL and runtime feature settings to HFL .env."""

import argparse
import os
import pathlib
import re
import stat
import tempfile
from typing import Dict, List, Optional
from urllib.parse import SplitResult, urlsplit, urlunsplit


RUNTIME_KEYS = {
    "HFL_EMAIL_SIGNUP_ENABLED",
    "HFL_PLATFORM_GATEWAY_AUTO_DEPLOY",
    "TURNSTILE_ENABLED",
    "TURNSTILE_SITE_KEY",
    "TURNSTILE_SECRET_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_SECURITY",
    "EMAIL_FROM",
}
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def warn(message: str) -> None:
    print(f"[runtime-config] WARNING: {message}")


def require_regular_file(path: pathlib.Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise SystemExit(f"{label} does not exist: {path}") from exc
    if not stat.S_ISREG(mode) or path.is_symlink():
        raise SystemExit(f"{label} must be a regular file, not a symlink: {path}")


def parse_public_origin(value: str) -> Optional[SplitResult]:
    try:
        candidate = urlsplit(value)
        candidate.port
    except ValueError:
        return None
    if (
        candidate.scheme not in {"http", "https"}
        or not candidate.hostname
        or candidate.username
        or candidate.password
        or candidate.query
        or candidate.fragment
        or candidate.path not in {"", "/"}
        or re.search(r"\s", candidate.netloc)
    ):
        return None
    return candidate


def host_for_url(value: str) -> str:
    if ":" in value and not value.startswith("["):
        return f"[{value}]"
    return value


def comma_values(value: str, exclude_wildcard: bool = False) -> List[str]:
    items = []
    for item in value.split(","):
        item = item.strip()
        if item and not (exclude_wildcard and item == "*") and item not in items:
            items.append(item)
    return items


def append_unique(items: List[str], *values: str) -> None:
    for value in values:
        if value and value not in items:
            items.append(value)


def read_runtime_values(path: Optional[pathlib.Path]) -> Dict[str, str]:
    if path is None:
        return {}
    require_regular_file(path, "runtime environment file")
    os.chmod(str(path), 0o600)
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        key, separator, value = raw_line.partition("=")
        if not separator or key not in RUNTIME_KEYS or re.search(r"[\r\n]", value):
            warn(f"ignoring invalid staged runtime key {key!r}")
            continue
        values[key] = value
    return values


def smtp_runtime_updates(values: Dict[str, str]) -> Dict[str, str]:
    """Validate staged SMTP inputs and return Docker Compose environment updates."""
    names = (
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_SECURITY",
        "EMAIL_FROM",
    )
    present = [name for name in names if values.get(name, "") != ""]
    if not present:
        return {}
    missing = [name for name in names if values.get(name, "") == ""]
    if missing:
        raise SystemExit(
            "partial SMTP deployment configuration; missing: " + ", ".join(missing)
        )

    host = values["SMTP_HOST"].strip()
    username = values["SMTP_USERNAME"].strip()
    password = values["SMTP_PASSWORD"]
    security = values["SMTP_SECURITY"].strip().lower()
    from_email = values["EMAIL_FROM"].strip()
    if not host or re.search(r"\s", host):
        raise SystemExit("SMTP_HOST must be a non-empty hostname without whitespace")
    if not username or re.search(r"[\r\n]", username):
        raise SystemExit("SMTP_USERNAME must be non-empty and single-line")
    if not password or re.search(r"[\x00\r\n]", password):
        raise SystemExit("SMTP_PASSWORD must be non-empty and single-line")
    if not from_email or re.search(r"[\r\n]", from_email):
        raise SystemExit("EMAIL_FROM must be non-empty and single-line")
    try:
        port = int(values["SMTP_PORT"])
    except ValueError as exc:
        raise SystemExit("SMTP_PORT must be an integer between 1 and 65535") from exc
    if port < 1 or port > 65535:
        raise SystemExit("SMTP_PORT must be an integer between 1 and 65535")
    if security not in {"ssl", "starttls", "none"}:
        raise SystemExit("SMTP_SECURITY must be one of: ssl, starttls, none")

    return {
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "EMAIL_HOST": host,
        "EMAIL_PORT": str(port),
        "EMAIL_HOST_USER": username,
        "EMAIL_HOST_PASSWORD": password,
        "EMAIL_USE_TLS": "true" if security == "starttls" else "false",
        "EMAIL_USE_SSL": "true" if security == "ssl" else "false",
        "DEFAULT_FROM_EMAIL": from_email,
    }


def compose_env_value(value: str) -> str:
    """Quote values that must remain literal through Docker Compose interpolation."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "$$")
    )
    return f'"{escaped}"'


def atomic_write(path: pathlib.Path, lines: List[str]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = pathlib.Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
        os.replace(str(temporary), str(path))
        os.chmod(str(path), 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def apply_configuration(
    env_path: pathlib.Path,
    direct_host: str,
    public_url: str,
    runtime_path: Optional[pathlib.Path],
) -> None:
    require_regular_file(env_path, "environment file")
    lines = env_path.read_text(encoding="utf-8").splitlines()
    current = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if separator:
            current[key] = value

    updates: Dict[str, str] = {}
    runtime_values = read_runtime_values(runtime_path)
    if runtime_path is not None:
        signup_enabled = runtime_values.get("HFL_EMAIL_SIGNUP_ENABLED", "").lower()
        if signup_enabled != "false":
            raise SystemExit(
                "SaaS deployment runtime configuration must disable email sign-up"
            )
        updates["HFL_EMAIL_SIGNUP_ENABLED"] = "false"
        updates.update(smtp_runtime_updates(runtime_values))

        gateway_enabled = runtime_values.get(
            "HFL_PLATFORM_GATEWAY_AUTO_DEPLOY", ""
        ).lower()
        if gateway_enabled in {"true", "false"}:
            updates["HFL_PLATFORM_GATEWAY_AUTO_DEPLOY"] = gateway_enabled
        else:
            warn(
                "invalid platform Gateway auto-deploy value; preserving installed value"
            )

        enabled = runtime_values.get("TURNSTILE_ENABLED", "").lower()
        if enabled in {"true", "false"}:
            updates["TURNSTILE_ENABLED"] = enabled
        else:
            warn("invalid Turnstile enabled value; preserving installed value")

        for name in ("TURNSTILE_SITE_KEY", "TURNSTILE_SECRET_KEY"):
            value = runtime_values.get(name, "")
            if value and KEY_PATTERN.fullmatch(value):
                updates[name] = value
            else:
                warn(f"{name} is empty or malformed; preserving installed value")

    direct_host = direct_host.strip()
    if direct_host and (
        re.search(r"\s", direct_host) or re.search(r"[/@?#]", direct_host)
    ):
        warn("invalid direct host; preserving installed direct-host configuration")
        direct_host = ""
    direct_allowed_host = direct_host.strip("[]")
    direct_url_host = host_for_url(direct_host)
    allowed_hosts = comma_values(
        current.get("DJANGO_ALLOWED_HOSTS", ""), exclude_wildcard=True
    )
    csrf_origins = comma_values(current.get("CSRF_TRUSTED_ORIGINS", ""))
    cors_origins = comma_values(current.get("CORS_ALLOWED_ORIGINS", ""))
    append_unique(allowed_hosts, "localhost", "127.0.0.1", direct_allowed_host)
    append_unique(
        csrf_origins,
        "https://localhost:11443",
        "https://127.0.0.1:11443",
        f"https://{direct_url_host}:11443" if direct_url_host else "",
    )
    append_unique(
        cors_origins,
        "https://localhost:11443",
        "https://127.0.0.1:11443",
        f"https://{direct_url_host}:11443" if direct_url_host else "",
    )
    if direct_url_host:
        updates["HFL_ADMIN_PUBLIC_URL"] = f"https://{direct_url_host}:11444"

    public_url = public_url.strip()
    if public_url:
        parsed = parse_public_origin(public_url)
        if parsed:
            public_origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
            append_unique(allowed_hosts, parsed.hostname or "")
            append_unique(csrf_origins, public_origin)
            append_unique(cors_origins, public_origin)
            updates.update(
                {
                    "FRONTEND_URL": public_origin,
                    "LENS_GATEWAY_BASE_URL": f"{public_origin}/sourcelens",
                }
            )
        else:
            warn(
                f"invalid public URL {public_url!r}; preserving installed URL configuration"
            )
    else:
        warn("public URL is empty; preserving installed URL configuration")

    updates["DJANGO_ALLOWED_HOSTS"] = ",".join(allowed_hosts)
    updates["CSRF_TRUSTED_ORIGINS"] = ",".join(csrf_origins)
    updates["CORS_ALLOWED_ORIGINS"] = ",".join(cors_origins)

    updated = []
    seen = set()
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else ""
        if key in updates:
            value = updates[key]
            if key == "EMAIL_HOST_PASSWORD":
                value = compose_env_value(value)
            updated.append(f"{key}={value}")
            seen.add(key)
        else:
            updated.append(line)
    for key, value in updates.items():
        if key not in seen:
            if key == "EMAIL_HOST_PASSWORD":
                value = compose_env_value(value)
            updated.append(f"{key}={value}")
    atomic_write(env_path, updated)
    print("[runtime-config] Applied deployment configuration before service startup")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=pathlib.Path)
    parser.add_argument("--direct-host", default="")
    parser.add_argument("--public-url", default="")
    parser.add_argument("--runtime-env-file", type=pathlib.Path)
    arguments = parser.parse_args()
    apply_configuration(
        arguments.env_file,
        arguments.direct_host,
        arguments.public_url,
        arguments.runtime_env_file,
    )


if __name__ == "__main__":
    main()
