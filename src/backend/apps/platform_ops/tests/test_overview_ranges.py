from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.platform_ops.selectors.internal.overview import _failed_task_count
from apps.task.models import Task


class PlatformOverviewRangeTests(TestCase):
    def _task(self, *, status: str, finished_at) -> Task:
        return Task.objects.create(
            organization_id=1,
            task_type=Task.Type.BACKUP,
            display_name=f"Task {status}",
            status=status,
            finished_at=finished_at,
        )

    def test_failed_task_count_uses_requested_time_range(self):
        now = timezone.now()
        self._task(status=Task.Status.FAILED, finished_at=now - timedelta(minutes=30))
        self._task(status=Task.Status.TIMEOUT, finished_at=now - timedelta(hours=2))
        self._task(status=Task.Status.SUCCESS, finished_at=now - timedelta(minutes=10))

        self.assertEqual(
            _failed_task_count(since=now - timedelta(hours=1), until=now),
            1,
        )
        self.assertEqual(
            _failed_task_count(since=now - timedelta(hours=3), until=now),
            2,
        )
