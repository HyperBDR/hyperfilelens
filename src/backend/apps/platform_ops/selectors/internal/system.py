"""System health probes for Platform Ops."""

from __future__ import annotations

import os

from django.conf import settings
from django.db import connection
from django.utils import timezone


def probe_database() -> dict:
    started = timezone.now()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        latency_ms = int((timezone.now() - started).total_seconds() * 1000)
        db = settings.DATABASES.get("default", {})
        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "engine": db.get("ENGINE", ""),
            "name": db.get("NAME", ""),
            "host": db.get("HOST", ""),
            "port": str(db.get("PORT", "")),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def probe_redis() -> dict:
    url = getattr(settings, "REDIS_URL", "") or os.getenv("REDIS_URL", "")
    if not url:
        return {"status": "unknown", "message": "REDIS_URL not configured"}
    try:
        import redis

        client = redis.from_url(url, socket_connect_timeout=2)
        started = timezone.now()
        client.ping()
        latency_ms = int((timezone.now() - started).total_seconds() * 1000)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def migration_status() -> list[dict]:
    from django.apps import apps
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    pending = {f"{app}.{name}" for app, name in plan}
    rows = []
    for app_config in sorted(apps.get_app_configs(), key=lambda a: a.label):
        if not app_config.name.startswith("apps."):
            continue
        loader = executor.loader
        applied = loader.applied_migrations
        for key, migration in sorted(loader.graph.nodes.items()):
            app_label, name = key
            if app_label != app_config.label:
                continue
            full = f"{app_label}.{name}"
            rows.append(
                {
                    "app": app_label,
                    "name": name,
                    "applied": full in applied,
                    "pending": full in pending,
                }
            )
    return rows


def table_row_counts() -> dict:
    from django.contrib.auth import get_user_model

    from apps.iam.models import Membership, Organization

    User = get_user_model()
    counts = {
        "users": User.objects.count(),
        "organizations": Organization.objects.count(),
        "memberships": Membership.objects.count(),
    }
    try:
        from apps.node.models import Node

        counts["nodes"] = Node.objects.count()
    except Exception:
        counts["nodes"] = 0
    try:
        from apps.task.models import Task

        counts["tasks"] = Task.objects.count()
    except Exception:
        counts["tasks"] = 0
    return counts


def probe_celery() -> dict:
    worker_count = 0
    active_tasks = 0
    celery_status = "unknown"
    celery_error = None

    try:
        from celery import current_app

        inspect = current_app.control.inspect(timeout=2)
        stats = inspect.stats() or {}
        active = inspect.active() or {}
        celery_status = "ok" if stats else "degraded"
        worker_count = len(stats)
        active_tasks = sum(len(tasks or []) for tasks in active.values())
    except Exception as exc:
        celery_status = "error"
        celery_error = str(exc)

    return {
        "status": celery_status,
        "worker_count": worker_count,
        "active_tasks": active_tasks,
        "error": celery_error,
    }


def system_health_payload() -> dict:
    return {
        "api": {"status": "ok"},
        "database": probe_database(),
        "redis": probe_redis(),
        "celery": probe_celery(),
        "checked_at": timezone.now().isoformat(),
    }


def deploy_profile_staff_payload() -> dict:
    from apps.platform_ops.services.internal.runtime_settings import (
        email_signup_enabled,
        platform_ops_allowed_cidrs,
        platform_ops_enabled,
        self_service_password_reset_enabled,
    )
    from common.deploy.site import tenant_public_url

    return {
        "platform_ops_enabled": platform_ops_enabled(),
        "email_signup_enabled": email_signup_enabled(),
        "self_service_password_reset": self_service_password_reset_enabled(),
        "tenant_public_url": tenant_public_url(),
        "platform_ops_allowed_cidrs": platform_ops_allowed_cidrs(),
        "app_version": os.getenv("APP_VERSION", "").strip() or None,
        "agent_version": os.getenv("AGENT_VERSION", "").strip() or None,
        "django_debug": bool(getattr(settings, "DEBUG", False)),
        "sentry_enabled": bool(getattr(settings, "SENTRY_ENABLED", False)),
        "sentry_environment": getattr(settings, "SENTRY_ENVIRONMENT", "") or None,
    }


def auth_policy_payload() -> dict:
    from apps.platform_ops.services.internal.runtime_settings import (
        google_client_id,
        google_oauth_enabled,
        turnstile_enabled,
        turnstile_secret_key,
        turnstile_site_key,
    )

    google_id = google_client_id()
    return {
        "turnstile_enabled": turnstile_enabled(),
        "google_oauth_configured": google_oauth_enabled(),
        "google_client_id_hint": google_id[-4:] if len(google_id) >= 4 else None,
        "turnstile_configured": bool(turnstile_site_key() and turnstile_secret_key()),
    }
