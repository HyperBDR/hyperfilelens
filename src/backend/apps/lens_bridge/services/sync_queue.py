"""Queue knowledge source sync jobs (Celery with thread fallback)."""

from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)


def queue_knowledge_source_sync(
    *,
    organization_id: int,
    knowledge_source_id: int,
    mode: str = "resume",
) -> None:
    execution_backend = str(
        getattr(settings, "LENS_KS_SYNC_EXECUTION_BACKEND", "celery") or "celery"
    ).strip().lower()
    if execution_backend != "celery":
        thread = threading.Thread(
            target=_run_sync_in_thread,
            kwargs={
                "organization_id": organization_id,
                "knowledge_source_id": knowledge_source_id,
                "mode": mode,
            },
            name=f"lens-ks-sync-{knowledge_source_id}",
            daemon=True,
        )
        thread.start()
        return

    from apps.lens_bridge.tasks.knowledge_source_sync import execute_knowledge_source_sync_task

    try:
        execute_knowledge_source_sync_task.delay(
            organization_id=organization_id,
            knowledge_source_id=knowledge_source_id,
            mode=mode,
        )
    except Exception:
        logger.exception(
            "Failed to queue knowledge source sync via Celery; falling back to thread "
            "ks_id=%s org_id=%s",
            knowledge_source_id,
            organization_id,
        )
        thread = threading.Thread(
            target=_run_sync_in_thread,
            kwargs={
                "organization_id": organization_id,
                "knowledge_source_id": knowledge_source_id,
                "mode": mode,
            },
            name=f"lens-ks-sync-{knowledge_source_id}",
            daemon=True,
        )
        thread.start()


def queue_sl_chat_user_provision(*, user_id: int, gateway_operator: bool = False) -> None:
    execution_backend = str(
        getattr(settings, "LENS_KS_SYNC_EXECUTION_BACKEND", "celery") or "celery"
    ).strip().lower()
    if execution_backend != "celery":
        thread = threading.Thread(
            target=_run_chat_user_provision_in_thread,
            kwargs={"user_id": user_id, "gateway_operator": gateway_operator},
            name=f"sl-chat-user-{user_id}",
            daemon=True,
        )
        thread.start()
        return

    from apps.lens_bridge.tasks.chat_user_provision import execute_chat_user_provision_task

    try:
        execute_chat_user_provision_task.delay(
            user_id=user_id,
            gateway_operator=gateway_operator,
        )
    except Exception:
        logger.exception(
            "Failed to queue SL chat user provision via Celery; falling back to thread user_id=%s",
            user_id,
        )
        thread = threading.Thread(
            target=_run_chat_user_provision_in_thread,
            kwargs={"user_id": user_id, "gateway_operator": gateway_operator},
            name=f"sl-chat-user-{user_id}",
            daemon=True,
        )
        thread.start()


def queue_copilot_chat_provision(*, session_link_id: int) -> None:
    """Queue a durable Copilot job.

    Copilot provisioning owns external resources and must never run in an API
    process daemon thread: a process restart would otherwise leave a chat
    permanently stuck in ``provisioning`` with partial SourceLens resources.
    """
    from apps.lens_bridge.tasks.chat_lifecycle import execute_copilot_chat_provision_task

    try:
        execute_copilot_chat_provision_task.delay(session_link_id=session_link_id)
    except Exception as exc:
        logger.exception("Failed to queue copilot chat provision via Celery session=%s", session_link_id)
        raise RuntimeError("Unable to queue chat provisioning.") from exc


def queue_copilot_chat_teardown(*, session_link_id: int) -> None:
    """Queue a durable Copilot teardown; no in-process fallback is allowed."""
    from apps.lens_bridge.tasks.chat_lifecycle import execute_copilot_chat_teardown_task

    try:
        execute_copilot_chat_teardown_task.delay(session_link_id=session_link_id)
    except Exception as exc:
        logger.exception("Failed to queue copilot chat teardown via Celery session=%s", session_link_id)
        raise RuntimeError("Unable to queue chat teardown.") from exc


def _run_chat_user_provision_in_thread(*, user_id: int, gateway_operator: bool) -> None:
    close_old_connections()
    from django.contrib.auth import get_user_model

    from apps.lens_bridge.services.chat_user_provisioning import ensure_sl_chat_user

    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return
    try:
        ensure_sl_chat_user(user, gateway_operator=gateway_operator)
    except Exception:
        logger.exception("SL chat user provision thread failed user_id=%s", user_id)


def _run_sync_in_thread(
    *,
    organization_id: int,
    knowledge_source_id: int,
    mode: str,
) -> None:
    close_old_connections()
    from apps.lens_bridge.services.knowledge_source_sync import run_knowledge_source_sync

    try:
        run_knowledge_source_sync(
            organization_id=organization_id,
            knowledge_source_id=knowledge_source_id,
        )
    except Exception:
        logger.exception(
            "Knowledge source sync thread failed ks_id=%s org_id=%s mode=%s",
            knowledge_source_id,
            organization_id,
            mode,
        )
