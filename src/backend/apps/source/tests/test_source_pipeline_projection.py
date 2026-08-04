from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.iam.models import Organization
from apps.node.models import Node
from apps.source.constants import PipelineStep, ResourceType, SelectableSourceKind
from apps.source.models import SourceBackupPipelineEntry, SourceResource
from apps.source.services.internal.source_pipeline import (
    ensure_pipeline_entry,
    revert_backup_flow_sources,
)


class SourcePipelineProjectionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="pipeline-projection", name="Pipeline Projection")
        self.agent = Node.objects.create(
            organization=self.org,
            name="agent-display",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            availability=Node.Availability.ONLINE,
            connection_ip_address="198.51.100.10",
            metadata={"inventory": {"hostname": "agent-reported"}},
        )

    def test_agent_projection_uses_hostname_and_connection_ip_fallback(self):
        entry = ensure_pipeline_entry(
            organization_id=self.org.id,
            source_kind=SelectableSourceKind.AGENT,
            ref_id=self.agent.id,
        )
        self.assertEqual(entry.source_name, "agent-display")
        self.assertEqual(entry.source_hostname, "agent-reported")
        self.assertEqual(entry.source_ip, "198.51.100.10")
        self.assertEqual(entry.source_status, Node.Status.ONLINE)
        self.assertEqual(entry.source_availability, Node.Availability.ONLINE)
        self.assertEqual(entry.created_at, self.agent.created_at)

    def test_nas_without_proxy_projects_empty_identity_and_offline(self):
        source = SourceResource.objects.create(
            organization=self.org,
            name="nas-without-proxy",
            resource_type=ResourceType.NAS,
            availability="online",
        )
        entry = ensure_pipeline_entry(
            organization_id=self.org.id,
            source_kind=SelectableSourceKind.NAS,
            ref_id=source.id,
        )
        self.assertEqual(entry.source_hostname, "")
        self.assertEqual(entry.source_ip, "")
        self.assertEqual(entry.source_availability, "offline")

    def test_deleted_entry_is_revived_with_refreshed_projection(self):
        entry = ensure_pipeline_entry(
            organization_id=self.org.id,
            source_kind=SelectableSourceKind.AGENT,
            ref_id=self.agent.id,
        )
        entry.soft_delete()
        self.agent.name = "renamed-agent"
        self.agent.save(update_fields=["name", "updated_at"])

        revived = ensure_pipeline_entry(
            organization_id=self.org.id,
            source_kind=SelectableSourceKind.AGENT,
            ref_id=self.agent.id,
        )

        self.assertEqual(revived.pk, entry.pk)
        self.assertFalse(revived.is_deleted)
        self.assertEqual(revived.source_name, "renamed-agent")

    def test_revert_to_step_one_keeps_explicit_pipeline_entry(self):
        entry = ensure_pipeline_entry(
            organization_id=self.org.id,
            source_kind=SelectableSourceKind.AGENT,
            ref_id=self.agent.id,
            step=PipelineStep.CONFIG,
        )
        entry.step = PipelineStep.CONFIG
        entry.save(update_fields=["step", "updated_at"])
        updated = revert_backup_flow_sources(
            organization_id=self.org.id,
            ids=[f"agent:{self.agent.id}"],
            target_step=PipelineStep.SOURCE_POOL,
        )
        self.assertEqual(updated, [f"agent:{self.agent.id}"])
        entry.refresh_from_db()
        self.assertEqual(entry.step, PipelineStep.SOURCE_POOL)
        self.assertFalse(entry.is_deleted)


class RebuildSourcePipelineCommandTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="pipeline-rebuild", name="Pipeline Rebuild")
        self.agent = Node.objects.create(
            organization=self.org,
            name="rebuild-agent",
            role=Node.Role.AGENT,
        )

    def test_dry_run_then_apply_is_idempotent(self):
        dry_run = StringIO()
        call_command("rebuild_source_backup_pipeline", organization_id=self.org.id, stdout=dry_run)
        self.assertIn("missing=1", dry_run.getvalue())
        self.assertFalse(SourceBackupPipelineEntry.objects.exists())

        applied = StringIO()
        call_command("rebuild_source_backup_pipeline", organization_id=self.org.id, apply=True, stdout=applied)
        self.assertTrue(SourceBackupPipelineEntry.objects.filter(
            organization=self.org, source_kind="agent", ref_id=self.agent.id
        ).exists())

        second = StringIO()
        call_command("rebuild_source_backup_pipeline", organization_id=self.org.id, apply=True, stdout=second)
        self.assertIn("created=0", second.getvalue())
        self.assertIn("updated=0", second.getvalue())

    def test_apply_quarantines_stale_rows_and_reports_missing_proxy(self):
        stale = SourceBackupPipelineEntry.objects.create(
            organization=self.org,
            source_kind=SelectableSourceKind.NAS,
            ref_id=999999,
        )
        SourceResource.objects.create(
            organization=self.org,
            name="unbound-nas",
            resource_type=ResourceType.NAS,
        )

        output = StringIO()
        call_command("rebuild_source_backup_pipeline", organization_id=self.org.id, apply=True, stdout=output)

        stale.refresh_from_db()
        self.assertTrue(stale.is_deleted)
        self.assertIn("quarantined=1", output.getvalue())
        self.assertIn("nas_without_proxy=1", output.getvalue())

    def test_rejects_invalid_batch_size(self):
        with self.assertRaises(CommandError):
            call_command("rebuild_source_backup_pipeline", batch_size=0)
