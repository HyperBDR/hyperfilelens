"""
Node write-path facade — other apps import this module only.

Agent execution:

- **Async** — ``run_agent_task_async``: returns ``task_id`` immediately; poll with
  ``apps.node.selectors`` (``get_node_task``, ``get_node_task_runtime_info``).
- **Sync** — ``run_agent_task_sync``: blocks on Redis ``task_stream`` until
  terminal or timeout (short tasks, e.g. browse directory).

WS lifecycle hooks (``record_task_progress``, ``complete_task``, …) are for
``apps.node.ws`` only; business apps should not call them directly.
"""

from apps.node.services.internal.agent_uninstall import (
    remove_agent_node,
    remove_agent_node_for_source_resource,
)
from apps.node.services.internal.agent_task import (
    AgentTaskHandle,
    AgentTaskSyncResult,
    cancel_agent_task,
    run_agent_task_async,
    run_agent_task_sync,
    wait_for_agent_task,
)
from apps.node.services.internal.node_registry import reconcile_stale_online_nodes
from apps.node.services.internal.task import (
    DispatchResult,
    cancel_task,
    complete_task,
    deliver_agent_task,
    dispatch_task,
    fail_active_tasks_for_node,
    record_task_progress,
    redeliver_pending_agent_task,
    sweep_watchdog_timeouts,
)

__all__ = [
    "AgentTaskHandle",
    "AgentTaskSyncResult",
    "DispatchResult",
    "cancel_agent_task",
    "cancel_task",
    "complete_task",
    "deliver_agent_task",
    "dispatch_task",
    "fail_active_tasks_for_node",
    "record_task_progress",
    "redeliver_pending_agent_task",
    "reconcile_stale_online_nodes",
    "remove_agent_node",
    "remove_agent_node_for_source_resource",
    "run_agent_task_async",
    "run_agent_task_sync",
    "sweep_watchdog_timeouts",
    "wait_for_agent_task",
]
