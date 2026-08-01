"""Shared maintenance gate for independently upgraded SourceLens runtime."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from django.core.cache import cache
from django.db import connection, transaction


_KEY = "lens_bridge:sourcelens_maintenance"
_FAILSAFE_TIMEOUT_SECONDS = 2 * 60 * 60
_RUN_GATE_LOCK_ID = 0x48464C534C52  # "HFLSLR"


def _acquire_run_gate_lock(*, shared: bool) -> None:
    function = "pg_advisory_xact_lock_shared" if shared else "pg_advisory_xact_lock"
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {function}(%s)", [_RUN_GATE_LOCK_ID])


@contextmanager
def sourcelens_run_creation_guard() -> Iterator[None]:
    """Serialize Run creation against the maintenance-start barrier."""
    with transaction.atomic():
        _acquire_run_gate_lock(shared=True)
        yield


def arm_sourcelens_maintenance() -> None:
    """Wait for in-flight Run creation, then atomically close the Run gate."""
    with transaction.atomic():
        _acquire_run_gate_lock(shared=False)
        begin_sourcelens_maintenance()


def begin_sourcelens_maintenance() -> None:
    # A normal installer always clears the gate.  Keep a fail-safe lease so a
    # hard-killed deployment host cannot leave AI Runs disabled forever.
    cache.set(_KEY, True, timeout=_FAILSAFE_TIMEOUT_SECONDS)


def end_sourcelens_maintenance() -> None:
    cache.delete(_KEY)


def sourcelens_maintenance_active() -> bool:
    return bool(cache.get(_KEY, False))
