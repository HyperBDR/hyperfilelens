"""Tests for privacy-safe optional Sentry initialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from common.observability.context import org_key_var, request_id_var, user_id_var
from common.observability.sentry import init_sentry


@pytest.fixture(autouse=True)
def _clear_sentry_env(monkeypatch):
    for name in (
        "SENTRY_ENABLED",
        "SENTRY_BACKEND_DSN",
        "SENTRY_DSN",
        "SENTRY_ENVIRONMENT",
        "SENTRY_RELEASE",
        "SENTRY_TRACES_SAMPLE_RATE",
        "SENTRY_COMPONENT",
        "SENTRY_SERVICE",
        "SECRET_KEY",
        "APP_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)


def test_init_sentry_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("SENTRY_BACKEND_DSN", "https://public@sentry.example.com/1")
    with patch("sentry_sdk.init") as mock_init:
        init_sentry()
    mock_init.assert_not_called()


@pytest.mark.parametrize(
    "dsn",
    ["", "not-a-dsn", "ftp://public@sentry.example.com/1", "https://sentry.example.com/1"],
)
def test_init_sentry_skips_invalid_dsn(monkeypatch, dsn):
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_BACKEND_DSN", dsn)
    with patch("sentry_sdk.init") as mock_init:
        init_sentry()
    mock_init.assert_not_called()


def test_init_sentry_uses_fixed_privacy_policy(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_BACKEND_DSN", "https://public@sentry.example.com/42")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "hfl-preprod")
    monkeypatch.setenv("SENTRY_RELEASE", "hyperfilelens-backend@0.1.8")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")

    fake_django = MagicMock(name="DjangoIntegration")
    fake_celery = MagicMock(name="CeleryIntegration")
    fake_redis = MagicMock(name="RedisIntegration")
    with (
        patch("sentry_sdk.init") as mock_init,
        patch("sentry_sdk.integrations.django.DjangoIntegration", return_value=fake_django),
        patch("sentry_sdk.integrations.celery.CeleryIntegration", return_value=fake_celery),
        patch("sentry_sdk.integrations.redis.RedisIntegration", return_value=fake_redis),
    ):
        init_sentry()

    kwargs = mock_init.call_args.kwargs
    assert kwargs["environment"] == "hfl-preprod"
    assert kwargs["release"] == "hyperfilelens-backend@0.1.8"
    assert kwargs["traces_sample_rate"] == 0.25
    assert kwargs["profiles_sample_rate"] == 0.0
    assert kwargs["send_default_pii"] is False
    assert kwargs["include_local_variables"] is False
    assert kwargs["max_request_body_size"] == "never"
    assert kwargs["before_send_transaction"] is kwargs["before_send"]
    assert kwargs["integrations"] == [fake_django, fake_celery, fake_redis]


def test_before_send_scrubs_pii_and_hashes_context(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_BACKEND_DSN", "https://public@sentry.example.com/42")
    monkeypatch.setenv("SECRET_KEY", "deployment-secret")
    monkeypatch.setenv("SENTRY_COMPONENT", "hfl-backend")
    monkeypatch.setenv("SENTRY_SERVICE", "api")
    request_id_var.set("trace-123")
    org_key_var.set("raw-organization")
    user_id_var.set("raw-user")

    with patch("sentry_sdk.init") as mock_init:
        init_sentry()
    before_send = mock_init.call_args.kwargs["before_send"]
    event = before_send(
        {
            "user": {"email": "person@example.com"},
            "request": {
                "url": "https://app.example.com/api/source/private?token=secret",
                "cookies": {"session": "secret"},
                "data": {"password": "secret"},
                "query_string": "token=secret",
                "headers": {"Authorization": "Bearer secret", "User-Agent": "pytest"},
                "env": {"REMOTE_ADDR": "192.0.2.15", "customer": "private"},
            },
            "transaction": "/api/source/private-id",
            "transaction_info": {"source": "url", "private": "customer"},
            "spans": [
                {
                    "trace_id": "trace-span-1",
                    "span_id": "span-1",
                    "op": "db.sql.query",
                    "description": "SELECT * FROM private_files WHERE owner='customer'",
                    "data": {"db.statement": "/customer/private"},
                    "tags": {"customer": "raw-organization"},
                }
            ],
            "message": "customer prompt and response",
            "logentry": {"message": "customer filename"},
            "breadcrumbs": [{"message": "customer path"}],
            "extra": {"args": ["/customer/private"], "safe_count": 2},
            "contexts": {
                "customer": {"content": "private"},
                "runtime": {"name": "CPython", "private": "customer"},
                "trace": {"trace_id": "abc", "data": {"path": "/customer/private"}},
            },
            "exception": {
                "values": [
                    {
                        "value": "open /customer/private failed",
                        "mechanism": {"type": "generic", "data": {"path": "/customer/private"}},
                        "stacktrace": {"frames": [{"vars": {"token": "secret"}}]},
                    }
                ]
            },
        },
        {},
    )

    assert "user" not in event
    assert event["request"] == {
        "url": "https://app.example.com",
        "headers": {},
    }
    for key in ("breadcrumbs", "extra", "fingerprint", "logentry", "message"):
        assert key not in event
    assert event["contexts"] == {
        "runtime": {"name": "CPython"},
        "trace": {"trace_id": "abc"},
    }
    exception = event["exception"]["values"][0]
    assert exception["value"] == "[Filtered]"
    assert "data" not in exception["mechanism"]
    assert "vars" not in exception["stacktrace"]["frames"][0]
    assert event["tags"]["trace_id"] == "trace-123"
    assert event["tags"]["org_hash"] != "raw-organization"
    assert event["tags"]["user_hash"] != "raw-user"
    assert event["tags"]["component"] == "hfl-backend"
    assert event["tags"]["service"] == "api"
    assert "raw-organization" not in str(event)
    assert "raw-user" not in str(event)
    assert "/customer/private" not in str(event)
    assert "transaction" not in event
    assert "transaction_info" not in event
    assert event["spans"] == [
        {
            "trace_id": "trace-span-1",
            "span_id": "span-1",
            "op": "db.sql.query",
        }
    ]
    assert "192.0.2.15" not in str(event)


def test_before_send_retains_only_safe_route_transaction(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_BACKEND_DSN", "https://public@sentry.example.com/42")
    with patch("sentry_sdk.init") as mock_init:
        init_sentry()
    before_send = mock_init.call_args.kwargs["before_send"]

    event = before_send(
        {
            "transaction": "/api/sources/<uuid:source_id>",
            "transaction_info": {"source": "route", "private": "customer"},
        },
        {},
    )

    assert event["transaction"] == "/api/sources/<uuid:source_id>"
    assert event["transaction_info"] == {"source": "route"}


def test_before_send_removes_url_credentials(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_BACKEND_DSN", "https://public@sentry.example.com/42")
    with patch("sentry_sdk.init") as mock_init:
        init_sentry()
    before_send = mock_init.call_args.kwargs["before_send"]
    event = before_send(
        {"request": {"url": "https://user:password@example.com:8443/private?token=secret"}},
        {},
    )
    assert event["request"]["url"] == "https://example.com:8443"


def test_init_failure_is_non_blocking(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_BACKEND_DSN", "https://public@sentry.example.com/42")
    with patch("sentry_sdk.init", side_effect=ValueError("bad config")):
        init_sentry()
