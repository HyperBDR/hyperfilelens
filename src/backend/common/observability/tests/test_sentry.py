"""Tests for optional Sentry initialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from common.observability.sentry import init_sentry


@pytest.fixture(autouse=True)
def _clear_sentry_env(monkeypatch):
    for name in (
        "SENTRY_ENABLED",
        "SENTRY_DSN",
        "SENTRY_ENVIRONMENT",
        "SENTRY_RELEASE",
        "SENTRY_TRACES_SAMPLE_RATE",
        "SENTRY_PROFILES_SAMPLE_RATE",
        "SENTRY_PROFILING_SAMPLE_RATE",
        "SENTRY_SEND_DEFAULT_PII",
        "ENV",
        "APP_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)


def test_init_sentry_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")

    with patch("sentry_sdk.init") as mock_init:
        init_sentry()

    mock_init.assert_not_called()


def test_init_sentry_skips_when_enabled_without_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "true")

    with patch("sentry_sdk.init") as mock_init:
        init_sentry()

    mock_init.assert_not_called()


def test_init_sentry_initializes_with_redis_integration(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "true")
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
    monkeypatch.setenv("SENTRY_RELEASE", "1.2.3")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")
    monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", "true")

    fake_django = MagicMock(name="DjangoIntegration")
    fake_celery = MagicMock(name="CeleryIntegration")
    fake_redis = MagicMock(name="RedisIntegration")

    with (
        patch("sentry_sdk.init") as mock_init,
        patch(
            "sentry_sdk.integrations.django.DjangoIntegration",
            return_value=fake_django,
        ),
        patch(
            "sentry_sdk.integrations.celery.CeleryIntegration",
            return_value=fake_celery,
        ),
        patch(
            "sentry_sdk.integrations.redis.RedisIntegration",
            return_value=fake_redis,
        ),
    ):
        init_sentry()

    mock_init.assert_called_once()
    kwargs = mock_init.call_args.kwargs
    assert kwargs["dsn"] == "https://example@sentry.io/1"
    assert kwargs["environment"] == "staging"
    assert kwargs["release"] == "1.2.3"
    assert kwargs["traces_sample_rate"] == 0.25
    assert kwargs["profiles_sample_rate"] == 0.1
    assert kwargs["send_default_pii"] is True
    assert kwargs["integrations"] == [fake_django, fake_celery, fake_redis]
    assert kwargs["before_send"] is not None


def test_init_sentry_clamps_sample_rates(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "1")
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "2")
    monkeypatch.setenv("SENTRY_PROFILING_SAMPLE_RATE", "-0.5")

    with patch("sentry_sdk.init") as mock_init:
        init_sentry()

    kwargs = mock_init.call_args.kwargs
    assert kwargs["traces_sample_rate"] == 1.0
    assert kwargs["profiles_sample_rate"] == 0.0


def test_init_sentry_falls_back_to_env_and_app_version(monkeypatch):
    monkeypatch.setenv("SENTRY_ENABLED", "yes")
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APP_VERSION", "9.9.9")

    with patch("sentry_sdk.init") as mock_init:
        init_sentry()

    kwargs = mock_init.call_args.kwargs
    assert kwargs["environment"] == "production"
    assert kwargs["release"] == "9.9.9"
