"""Deployment secrets and endpoints for LLM providers (runtime overlay with env fallback)."""

from __future__ import annotations

from apps.platform_ops.services.internal import runtime_settings as runtime


def openai_api_key() -> str | None:
    return runtime.openai_api_key()


def openai_api_base() -> str:
    return runtime.openai_api_base()


def azure_openai_api_key() -> str | None:
    return runtime.azure_openai_api_key()


def azure_openai_api_base() -> str | None:
    return runtime.azure_openai_api_base()


def gemini_api_key() -> str | None:
    return runtime.gemini_api_key()


def langfuse_public_key() -> str:
    return runtime.langfuse_public_key()


def langfuse_secret_key() -> str:
    return runtime.langfuse_secret_key()


def langfuse_host() -> str:
    return runtime.langfuse_base_url()


def langfuse_enabled_by_env() -> bool:
    return runtime.langfuse_enabled()
