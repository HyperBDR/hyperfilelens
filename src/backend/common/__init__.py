"""Platform layer (package ``common``): shared HTTP, observability, scheduling.

HyperFileLens control-plane infrastructure shared by all business apps:
transport shape, observability, i18n, security hooks, and Celery scheduling.
No domain models or business rules live here.

Package name is ``common`` (not ``platform``) to avoid shadowing the Python
stdlib ``platform`` module when ``src/backend`` is on ``sys.path``.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
