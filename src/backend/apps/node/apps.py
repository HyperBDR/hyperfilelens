"""
Node app config (agent registry, enrollment, task deliveries).
"""

from django.apps import AppConfig


class NodeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.node"
    label = "node"
    verbose_name = "Node"

    def ready(self) -> None:
        from apps.node import signals  # noqa: F401
        from apps.node.ws.lifecycle import ensure_ws_instance_keepalive_started

        ensure_ws_instance_keepalive_started()
