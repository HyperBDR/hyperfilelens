from __future__ import annotations

import socket
import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand, CommandError

from apps.node import conf as node_conf
from apps.node.models import NodeTask
from apps.node.services.internal import redis_store
from apps.node.ws.groups import ws_instance_group_name


class Command(BaseCommand):
    help = "Begin, complete, or check the WebSocket recovery delivery gate."

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=("begin", "complete", "check", "drain", "reattach"),
        )
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8001)
        parser.add_argument("--timeout", type=int, default=60)
        parser.add_argument("--grace", type=int, default=3)
        parser.add_argument("--exclude-instance", action="append", default=[])

    @staticmethod
    def _socket_ready(*, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            return False

    def _ready(self, *, host: str, port: int) -> bool:
        return (
            self._socket_ready(host=host, port=port)
            and redis_store.has_live_ws_instance()
        )

    def handle(self, *args, **options):
        action = options["action"]
        host = options["host"]
        port = int(options["port"])
        if action == "drain":
            layer = get_channel_layer()
            if layer is None:
                raise CommandError("Channel layer unavailable; cannot drain WebSockets")
            async_to_sync(layer.group_send)(
                ws_instance_group_name(ws_instance_id=node_conf.WS_INSTANCE_ID),
                {"type": "deployment.drain", "reason": "control-plane upgrade"},
            )
            time.sleep(max(0, int(options["grace"])))
            self.stdout.write(
                f"WebSocket instance {node_conf.WS_INSTANCE_ID} drain requested"
            )
            return

        if action == "reattach":
            self._wait_for_active_task_nodes(
                timeout=int(options["timeout"]),
                excluded_instances=set(options["exclude_instance"]),
            )
            return

        if action == "begin":
            if not redis_store.begin_ws_recovery_hold():
                raise CommandError(
                    "Redis unavailable; failed to begin WebSocket recovery hold"
                )
            self.stdout.write("WebSocket recovery hold active")
            return

        if action == "check":
            if (
                not self._ready(host=host, port=port)
                or redis_store.ws_recovery_hold_active()
            ):
                raise CommandError(
                    "WebSocket route is not ready for Agent task delivery"
                )
            self.stdout.write("WebSocket route ready")
            return

        deadline = time.monotonic() + max(1, int(options["timeout"]))
        while time.monotonic() < deadline:
            if self._ready(host=host, port=port):
                if not redis_store.clear_ws_recovery_hold():
                    raise CommandError(
                        "Redis unavailable; failed to clear WebSocket recovery hold"
                    )
                self.stdout.write("WebSocket recovery hold cleared")
                return
            time.sleep(1)
        raise CommandError(
            f"WebSocket route did not become ready at {host}:{port} before timeout"
        )

    def _wait_for_active_task_nodes(
        self, *, timeout: int, excluded_instances: set[str]
    ) -> None:
        """Wait only for Agents that own accepted backup/restore work."""
        deadline = time.monotonic() + max(1, timeout)
        while time.monotonic() < deadline:
            node_ids = list(
                NodeTask.objects.filter(
                    status=NodeTask.Status.RUNNING,
                    correlation_type__in=(
                        "protection.backup",
                        "restore.record",
                        "restore.repository_server",
                    ),
                )
                .values_list("node_id", flat=True)
                .distinct()
            )
            missing = []
            for node_id in node_ids:
                ws_instance = redis_store.get_agent_location(agent_id=int(node_id))
                if not ws_instance or ws_instance in excluded_instances:
                    missing.append(node_id)
            if not missing:
                self.stdout.write(
                    f"Active task Agent reattach gate passed ({len(node_ids)} nodes)"
                )
                return
            time.sleep(1)
        raise CommandError(
            "Active backup/restore Agents did not reattach before timeout"
        )
