"""Process-level WebSocket instance keepalive (Daphne / ASGI workers)."""

from __future__ import annotations

import logging
import threading
import time

from apps.node import conf as node_conf
from apps.node.services.internal import redis_store

logger = logging.getLogger(__name__)

_keepalive_thread: threading.Thread | None = None
_started = False
_lock = threading.Lock()


def ensure_ws_instance_keepalive_started() -> None:
    """Touch ``node_alive`` periodically so multi-instance routing stays valid."""
    global _keepalive_thread, _started
    with _lock:
        if _started:
            return
        _started = True
        _keepalive_thread = threading.Thread(
            target=_keepalive_loop,
            name="ws-instance-keepalive",
            daemon=True,
        )
        _keepalive_thread.start()


def _keepalive_loop() -> None:
    interval = max(5, int(node_conf.WS_INSTANCE_KEEPALIVE_INTERVAL_SECONDS))
    while True:
        try:
            redis_store.touch_ws_instance_alive()
        except Exception:
            logger.debug("ws instance keepalive touch failed", exc_info=True)
        time.sleep(interval)
