"""Product task lifecycle signals."""

from django.dispatch import Signal

task_cancelled = Signal()
task_failed = Signal()
task_succeeded = Signal()
task_timed_out = Signal()
task_updated = Signal()
