# HFL_SENTRY_PRIVACY_ADAPTER=1
"""Apply HFL privacy policy before bundled SourceLens initializes Sentry."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_FILTERED = "[Filtered]"
_SAFE_CONTEXT_FIELDS = {
    "os": frozenset({"build", "kernel_version", "name", "version"}),
    "runtime": frozenset({"build", "name", "version"}),
    "trace": frozenset({"op", "origin", "parent_span_id", "span_id", "status", "trace_id"}),
}
_SAFE_SPAN_FIELDS = frozenset(
    {
        "op",
        "origin",
        "parent_span_id",
        "same_process_as_parent",
        "span_id",
        "start_timestamp",
        "status",
        "timestamp",
        "trace_id",
    }
)


def _safe_url(value: Any) -> str | None:
    """Return only the origin of an HTTP(S) URL."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    if port is not None:
        host = f"{host}:{port}"
    return urlunsplit((parsed.scheme, host, "", "", ""))


def _safe_spans(value: Any) -> list[dict[str, Any]]:
    """Retain trace topology and timing while dropping span payload content."""
    if not isinstance(value, list):
        return []
    spans: list[dict[str, Any]] = []
    for span in value:
        if not isinstance(span, Mapping):
            continue
        safe_span = {
            str(key): field
            for key, field in span.items()
            if str(key) in _SAFE_SPAN_FIELDS
            and isinstance(field, (bool, float, int, str))
        }
        if safe_span:
            spans.append(safe_span)
    return spans


def _scrub_event(event: dict[str, Any], hint: Any) -> dict[str, Any]:  # noqa: ARG001
    """Retain operational metadata while removing customer-controlled text."""
    event.pop("user", None)
    for key in ("breadcrumbs", "extra", "fingerprint", "logentry", "message"):
        event.pop(key, None)

    request = event.get("request")
    if isinstance(request, dict):
        safe_request: dict[str, Any] = {"headers": {}}
        if safe_request_url := _safe_url(request.get("url")):
            safe_request["url"] = safe_request_url
        event["request"] = safe_request

    transaction_info = event.get("transaction_info")
    route_transaction = (
        isinstance(transaction_info, Mapping)
        and transaction_info.get("source") == "route"
        and isinstance(event.get("transaction"), str)
    )
    if route_transaction:
        event["transaction_info"] = {"source": "route"}
    else:
        event.pop("transaction", None)
        event.pop("transaction_info", None)

    if spans := _safe_spans(event.get("spans")):
        event["spans"] = spans
    else:
        event.pop("spans", None)

    contexts = event.get("contexts")
    if isinstance(contexts, Mapping):
        event["contexts"] = {
            str(name): {
                str(key): value
                for key, value in context.items()
                if str(key) in _SAFE_CONTEXT_FIELDS[str(name)]
                and isinstance(value, (bool, float, int, str))
            }
            for name, context in contexts.items()
            if str(name) in _SAFE_CONTEXT_FIELDS and isinstance(context, Mapping)
        }
    else:
        event.pop("contexts", None)

    exception = event.get("exception")
    if isinstance(exception, dict):
        for value in exception.get("values") or []:
            if not isinstance(value, dict):
                continue
            if value.get("value"):
                value["value"] = _FILTERED
            mechanism = value.get("mechanism")
            if isinstance(mechanism, dict):
                mechanism.pop("data", None)
            stacktrace = value.get("stacktrace")
            if not isinstance(stacktrace, dict):
                continue
            for frame in stacktrace.get("frames") or []:
                if isinstance(frame, dict):
                    frame.pop("vars", None)

    tags = {
        "component": (os.getenv("SENTRY_COMPONENT") or "sourcelens").strip(),
        "deployment_mode": (os.getenv("SENTRY_DEPLOYMENT_MODE") or "bundled").strip(),
        "product": "hyperfilelens",
        "service": (os.getenv("SENTRY_SERVICE") or "unknown").strip(),
    }
    event["tags"] = {key: value for key, value in tags.items() if value}
    return event


def _scrub_breadcrumb(crumb: dict[str, Any], hint: Any) -> dict[str, Any]:  # noqa: ARG001
    """Drop breadcrumb text and retain only classification metadata."""
    return {
        key: crumb[key]
        for key in ("category", "level", "timestamp", "type")
        if key in crumb
    }


def _compose_event_hook(
    upstream: Callable[[dict[str, Any], Any], dict[str, Any] | None] | None,
) -> Callable[[dict[str, Any], Any], dict[str, Any] | None]:
    """Run an upstream filter before enforcing the HFL privacy policy."""

    def callback(event: dict[str, Any], hint: Any) -> dict[str, Any] | None:
        if upstream is not None:
            try:
                event = upstream(event, hint)
            except Exception:
                return None
            if event is None:
                return None
        return _scrub_event(event, hint)

    return callback


def _compose_breadcrumb_hook(
    upstream: Callable[[dict[str, Any], Any], dict[str, Any] | None] | None,
) -> Callable[[dict[str, Any], Any], dict[str, Any] | None]:
    """Run an upstream breadcrumb filter before removing customer text."""

    def callback(crumb: dict[str, Any], hint: Any) -> dict[str, Any] | None:
        if upstream is not None:
            try:
                crumb = upstream(crumb, hint)
            except Exception:
                return None
            if crumb is None:
                return None
        return _scrub_breadcrumb(crumb, hint)

    return callback


def _install_sentry_policy() -> None:
    """Wrap the SDK initializer without making SourceLens startup depend on it."""
    try:
        import sentry_sdk
    except ImportError:
        return
    if getattr(sentry_sdk.init, "_hfl_privacy_policy", False):
        return

    original_init = sentry_sdk.init

    def privacy_init(*args: Any, **options: Any) -> Any:
        options["before_send"] = _compose_event_hook(options.get("before_send"))
        options["before_send_transaction"] = _compose_event_hook(
            options.get("before_send_transaction")
        )
        options["before_breadcrumb"] = _compose_breadcrumb_hook(options.get("before_breadcrumb"))
        options["include_local_variables"] = False
        options["max_request_body_size"] = "never"
        options["profiles_sample_rate"] = 0.0
        options["send_default_pii"] = False
        try:
            return original_init(*args, **options)
        except Exception:
            os.environ["SENTRY_ENABLED"] = "false"
            os.environ["SENTRY_DSN"] = ""
            return None

    privacy_init._hfl_privacy_policy = True  # type: ignore[attr-defined]
    sentry_sdk.init = privacy_init


try:
    _install_sentry_policy()
except Exception:
    # Observability must never prevent SourceLens or LensNode startup.
    os.environ["SENTRY_ENABLED"] = "false"
    os.environ["SENTRY_DSN"] = ""
