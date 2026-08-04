from unittest import mock

from django.test import SimpleTestCase

from apps.source.periodic_tasks import register_periodic_tasks


class SourcePeriodicTaskTests(SimpleTestCase):
    @mock.patch("apps.source.periodic_tasks.TASK_REGISTRY.add")
    def test_registers_probe_unregister_and_pipeline_reconciliation(self, add):
        register_periodic_tasks()

        self.assertEqual(add.call_count, 4)
        add.assert_any_call(
            name="source_reconcile_backup_pipeline",
            task="apps.source.tasks.pipeline.reconcile_source_pipeline_task",
            schedule=60,
            args=(),
            kwargs={"limit": 100},
            queue=None,
            enabled=True,
        )
        add.assert_any_call(
            name="source_reconcile_availability",
            task=(
                "apps.source.tasks.connection_probe."
                "reconcile_source_availability_task"
            ),
            schedule=60,
            args=(),
            kwargs={"limit": 100},
            queue="source.remote-io",
            enabled=True,
        )
        add.assert_any_call(
            name="source_reconcile_stale_connection_probes",
            task=(
                "apps.source.tasks.connection_probe."
                "reconcile_stale_source_connection_probes_task"
            ),
            schedule=60,
            args=(),
            kwargs={"limit": 100},
            queue="source.remote-io",
            enabled=True,
        )
