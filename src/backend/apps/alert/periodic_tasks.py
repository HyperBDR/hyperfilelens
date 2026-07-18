"""Shim for platform ``register_periodic_tasks`` discovery."""

from apps.alert.tasks.periodic_tasks import register_periodic_tasks

__all__ = ["register_periodic_tasks"]
