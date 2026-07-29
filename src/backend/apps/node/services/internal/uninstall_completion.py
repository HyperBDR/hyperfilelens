"""Signed, one-time completion handling for detached Agent uninstall."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from django.core import signing
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from apps.node import conf as node_conf
from apps.node.models import NodeTask
from apps.node.services.internal.task import complete_task

_SIGNING_SALT = "node-agent-uninstall-completion"
UNINSTALL_COMPLETION_PATH = "/api/v1/node/agent-uninstall/completion/"


class UninstallCompletionError(ValueError):
    """Raised when a detached uninstall callback cannot be accepted."""


@dataclass(frozen=True)
class UninstallCompletionOutcome:
    """Authoritative result returned after processing one completion callback."""

    task_id: str
    node_id: int
    task_status: str
    cleanup_complete: bool
    idempotent: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "node_id": self.node_id,
            "task_status": self.task_status,
            "cleanup_complete": self.cleanup_complete,
            "idempotent": self.idempotent,
        }


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def attach_uninstall_completion(*, task: NodeTask) -> NodeTask:
    """Attach a signed callback token before the uninstall command is delivered."""
    if task.kind != "agent.uninstall":
        raise ValueError("uninstall completion can only be attached to agent.uninstall")

    nonce = str(uuid4())
    token = signing.dumps(
        {
            "task_id": str(task.id),
            "node_id": int(task.node_id),
            "nonce": nonce,
        },
        salt=_SIGNING_SALT,
        compress=True,
    )
    payload = dict(task.payload or {})
    payload["completion"] = {
        "path": UNINSTALL_COMPLETION_PATH,
        "token": token,
        "token_digest": _token_digest(token),
        "expires_in_seconds": int(node_conf.UNINSTALL_COMPLETION_MAX_AGE_SECONDS),
    }
    task.payload = payload
    task.save(update_fields=["payload", "updated_at"])
    return task


def _validated_token_payload(token: str) -> dict[str, Any]:
    try:
        payload = signing.loads(
            token,
            salt=_SIGNING_SALT,
            max_age=node_conf.UNINSTALL_COMPLETION_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise UninstallCompletionError("completion token expired") from exc
    except signing.BadSignature as exc:
        raise UninstallCompletionError("invalid completion token") from exc
    if not isinstance(payload, dict):
        raise UninstallCompletionError("invalid completion token payload")
    return payload


@transaction.atomic
def complete_detached_uninstall(
    *,
    token: str,
    cleanup_complete: bool,
    cleanup_failures: list[dict[str, Any]] | None = None,
    retained_resources: list[str] | None = None,
) -> UninstallCompletionOutcome:
    """Consume one completion token and finalize its NodeTask exactly once."""
    clean_token = str(token or "").strip()
    if not clean_token:
        raise UninstallCompletionError("completion token is required")
    signed = _validated_token_payload(clean_token)
    task_id = str(signed.get("task_id") or "").strip()
    node_id = int(signed.get("node_id") or 0)
    if not task_id or node_id <= 0:
        raise UninstallCompletionError("completion token is missing task identity")

    task = (
        NodeTask.objects.select_for_update()
        .filter(pk=task_id, node_id=node_id, kind="agent.uninstall")
        .first()
    )
    if task is None:
        raise UninstallCompletionError("uninstall task was not found")

    result = dict(task.result or {})
    if result.get("completion_received_at"):
        return UninstallCompletionOutcome(
            task_id=str(task.id),
            node_id=int(task.node_id),
            task_status=str(task.status),
            cleanup_complete=bool(result.get("cleanup_complete")),
            idempotent=True,
        )

    task_payload = dict(task.payload or {})
    completion = task_payload.get("completion")
    if not isinstance(completion, dict) or not constant_time_compare(
        str(completion.get("token_digest") or ""),
        _token_digest(clean_token),
    ):
        raise UninstallCompletionError("completion token does not match the task")

    failures = [
        {
            "code": str(item.get("code") or "cleanup_failed")[:100],
            "detail": str(item.get("detail") or "Cleanup failed.")[:2000],
        }
        for item in (cleanup_failures or [])[:100]
        if isinstance(item, dict)
    ]
    retained = [
        str(item)[:1000]
        for item in (retained_resources or [])[:100]
        if str(item).strip()
    ]
    effective_cleanup_complete = bool(
        cleanup_complete and not failures and not retained
    )
    force_cleanup = bool(task_payload.get("force_cleanup"))
    completion_state = dict(completion)
    completion_state.pop("token", None)
    completion_state["used_at"] = timezone.now().isoformat()
    task_payload["completion"] = completion_state
    task.payload = task_payload
    task.save(update_fields=["payload", "updated_at"])
    result.pop("completion_timed_out_at", None)
    result.update(
        {
            "mode": "local_detached",
            "completion_received_at": timezone.now().isoformat(),
            "cleanup_complete": effective_cleanup_complete,
            "cleanup_failures": failures,
            "retained_resources": retained,
            "force": force_cleanup,
            "outcome": (
                "cleanup_success"
                if effective_cleanup_complete
                else "force_cleanup_success"
                if force_cleanup
                else "cleanup_failed"
            ),
        }
    )
    terminal_status = (
        NodeTask.Status.SUCCESS
        if effective_cleanup_complete or force_cleanup
        else NodeTask.Status.FAILED
    )
    error = ""
    if not effective_cleanup_complete:
        error = "; ".join(
            str(item.get("detail") or item.get("code") or "cleanup failed")
            for item in failures
        )[:2000] or "Detached uninstall reported incomplete cleanup."
    completed = complete_task(
        task_id=task.id,
        node_id=task.node_id,
        status=terminal_status,
        result=result,
        error=error,
        replace_result=True,
    )

    from apps.node.tasks.lifecycle import advance_node_lifecycle_for_node

    source_unregister_task_id = int(
        task_payload.get("source_unregister_task_id") or 0
    )
    transaction.on_commit(
        lambda: advance_node_lifecycle_for_node.apply_async(
            kwargs={"node_id": int(task.node_id)},
        )
    )
    if source_unregister_task_id > 0:
        from apps.source.tasks.source_unregister import queue_source_unregister_task

        transaction.on_commit(
            lambda: queue_source_unregister_task(
                task_id=source_unregister_task_id,
                countdown_seconds=1,
            )
        )
    return UninstallCompletionOutcome(
        task_id=str(completed.id),
        node_id=int(completed.node_id),
        task_status=str(completed.status),
        cleanup_complete=effective_cleanup_complete,
    )


__all__ = [
    "UNINSTALL_COMPLETION_PATH",
    "UninstallCompletionError",
    "UninstallCompletionOutcome",
    "attach_uninstall_completion",
    "complete_detached_uninstall",
]
