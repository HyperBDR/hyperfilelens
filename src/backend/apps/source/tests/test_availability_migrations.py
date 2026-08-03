from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class AvailabilityMigrationTests(TransactionTestCase):
    migrate_from = [
        ("node", "0008_nodetask_requesting_organization"),
        ("source", "0009_repository_purge_pending_idempotency_key"),
    ]
    migrate_to = [
        ("node", "0009_node_availability"),
        ("source", "0010_source_resource_availability"),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        self._seed_history(old_apps)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _seed_history(self, apps):
        Organization = apps.get_model("iam", "Organization")
        Node = apps.get_model("node", "Node")
        SourceResource = apps.get_model("source", "SourceResource")
        org = Organization.objects.create(
            key="availability-migration",
            name="Availability migration",
        )
        now = timezone.now()
        agent = Node.objects.create(
            organization=org,
            name="fresh-agent",
            role="agent",
            status="online",
            last_seen_at=now,
        )
        stale_agent = Node.objects.create(
            organization=org,
            name="stale-agent",
            role="agent",
            status="online",
            last_seen_at=now - timedelta(minutes=5),
        )
        proxy = Node.objects.create(
            organization=org,
            name="fresh-proxy",
            role="proxy",
            status="online",
            last_seen_at=now,
        )
        SourceResource.objects.create(
            organization=org,
            name="local-fresh",
            resource_type="local",
            bound_node=agent,
        )
        SourceResource.objects.create(
            organization=org,
            name="local-stale",
            resource_type="local",
            bound_node=stale_agent,
        )
        SourceResource.objects.create(
            organization=org,
            name="nas-proven",
            resource_type="nas",
            bound_node=proxy,
            connection_test_status="success",
            last_connection_test=now,
        )
        SourceResource.objects.create(
            organization=org,
            name="nas-unproven",
            resource_type="nas",
            bound_node=proxy,
        )

    def test_backfills_only_persisted_fresh_evidence_online(self):
        Node = self.apps.get_model("node", "Node")
        SourceResource = self.apps.get_model("source", "SourceResource")

        self.assertEqual(
            Node.objects.get(name="fresh-agent").availability,
            "online",
        )
        self.assertEqual(
            Node.objects.get(name="stale-agent").availability,
            "offline",
        )
        self.assertEqual(
            SourceResource.objects.get(name="local-fresh").availability,
            "online",
        )
        self.assertEqual(
            SourceResource.objects.get(name="local-stale").availability,
            "offline",
        )
        self.assertEqual(
            SourceResource.objects.get(name="nas-proven").availability,
            "online",
        )
        self.assertEqual(
            SourceResource.objects.get(name="nas-unproven").availability,
            "offline",
        )
