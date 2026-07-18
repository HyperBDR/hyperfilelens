"""
Shim for platform ``register_periodic_tasks`` discovery (see common/management).

Implementation lives in ``tasks/periodic_tasks.py`` per APP directory standard.
"""

from apps.node.tasks.periodic_tasks import register_periodic_tasks

__all__ = ["register_periodic_tasks"]
