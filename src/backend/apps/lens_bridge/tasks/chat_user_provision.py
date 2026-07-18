from __future__ import annotations

import logging

from celery import shared_task

from common.observability.celery_context import celery_trace

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.lens_bridge.tasks.chat_user_provision.execute_chat_user_provision_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    soft_time_limit=120,
    time_limit=180,
)
def execute_chat_user_provision_task(
    self,
    *,
    user_id: int,
    gateway_operator: bool = False,
) -> dict:
    trace_id = f"sl-chat-user-{user_id}"
    with celery_trace(trace_id, task_name="apps.lens_bridge.tasks.chat_user_provision.execute_chat_user_provision_task"):
        from django.contrib.auth import get_user_model

        from apps.lens_bridge.services.chat_user_provisioning import ensure_sl_chat_user

        user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            logger.warning("chat user provision skipped: user_id=%s not found", user_id)
            return {"status": "skipped", "reason": "user_not_found"}

        link = ensure_sl_chat_user(user, gateway_operator=gateway_operator)
        logger.info(
            "chat user provision finished user_id=%s sl_user_id=%s status=%s",
            user_id,
            link.sl_user_id,
            link.provision_status,
        )
        return {
            "status": link.provision_status,
            "sl_user_id": link.sl_user_id,
            "sl_username": link.sl_username,
        }
