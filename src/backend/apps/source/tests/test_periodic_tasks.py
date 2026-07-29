from unittest import mock

from django.test import SimpleTestCase

from apps.source.periodic_tasks import register_periodic_tasks


class SourcePeriodicTaskTests(SimpleTestCase):
    @mock.patch("apps.source.periodic_tasks.TASK_REGISTRY.add")
    def test_registers_probe_and_unregister_reconciliation(self, add):
        register_periodic_tasks()

        self.assertEqual(add.call_count, 2)
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
