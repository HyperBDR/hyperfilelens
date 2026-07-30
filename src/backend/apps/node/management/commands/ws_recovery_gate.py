from __future__ import annotations

import socket
import time

from django.core.management.base import BaseCommand, CommandError

from apps.node.services.internal import redis_store


class Command(BaseCommand):
    help = "Begin, complete, or check the WebSocket recovery delivery gate."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=("begin", "complete", "check"))
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8001)
        parser.add_argument("--timeout", type=int, default=60)

    @staticmethod
    def _socket_ready(*, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            return False

    def _ready(self, *, host: str, port: int) -> bool:
        return self._socket_ready(host=host, port=port) and redis_store.has_live_ws_instance()

    def handle(self, *args, **options):
        action = options["action"]
        host = options["host"]
        port = int(options["port"])
        if action == "begin":
            if not redis_store.begin_ws_recovery_hold():
                raise CommandError("Redis unavailable; failed to begin WebSocket recovery hold")
            self.stdout.write("WebSocket recovery hold active")
            return

        if action == "check":
            if not self._ready(host=host, port=port) or redis_store.ws_recovery_hold_active():
                raise CommandError("WebSocket route is not ready for Agent task delivery")
            self.stdout.write("WebSocket route ready")
            return

        deadline = time.monotonic() + max(1, int(options["timeout"]))
        while time.monotonic() < deadline:
            if self._ready(host=host, port=port):
                if not redis_store.clear_ws_recovery_hold():
                    raise CommandError("Redis unavailable; failed to clear WebSocket recovery hold")
                self.stdout.write("WebSocket recovery hold cleared")
                return
            time.sleep(1)
        raise CommandError(
            f"WebSocket route did not become ready at {host}:{port} before timeout"
        )
