import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from apps.protection.models import BackupConfig, BackupPolicy, BackupSourceSnapshot, FileFilterRule
from apps.protection.services.backup_runtime_policy import (
    SYSTEM_NEVER_COMPRESS_EXTENSIONS,
    build_backup_runtime_policy,
    compression_agent_payload,
)


class CompressionRuntimePolicyTests(SimpleTestCase):
    def test_compression_levels_map_to_complete_internal_profiles(self):
        cases = (
            (BackupConfig.CompressionLevel.NONE, "none", 0, ()),
            (BackupConfig.CompressionLevel.BALANCED, "zstd", 4096, SYSTEM_NEVER_COMPRESS_EXTENSIONS),
            (
                BackupConfig.CompressionLevel.HIGH,
                "zstd-better-compression",
                4096,
                SYSTEM_NEVER_COMPRESS_EXTENSIONS,
            ),
        )

        for level, compressor, minimum_size, never_extensions in cases:
            with self.subTest(level=level):
                payload = compression_agent_payload(level)
                self.assertEqual(payload["level"], level)
                self.assertEqual(payload["compressor"], compressor)
                self.assertEqual(payload["minimum_file_size_bytes"], minimum_size)
                self.assertEqual(payload["maximum_file_size_bytes"], 0)
                self.assertEqual(payload["only_extensions"], [])
                self.assertEqual(payload["never_extensions"], list(never_extensions))

    def test_compression_payload_lists_are_isolated(self):
        first = compression_agent_payload(BackupConfig.CompressionLevel.BALANCED)
        first["never_extensions"].append(".invalid")

        second = compression_agent_payload(BackupConfig.CompressionLevel.BALANCED)

        self.assertNotIn(".invalid", second["never_extensions"])

    def test_compression_payload_rejects_unknown_level(self):
        with self.assertRaises(ValidationError):
            compression_agent_payload("best")


class RuntimePolicyDatabaseTests(TestCase):
    def setUp(self):
        self.config = BackupConfig.objects.create(
            organization_id=101,
            name="Runtime policy config",
            source_type="agent",
            source_ref_id=201,
            repository_id=301,
            compression_level=BackupConfig.CompressionLevel.BALANCED,
        )

    def test_policy_snapshot_preserves_inactive_bound_ids(self):
        file_filter = FileFilterRule.objects.create(
            organization_id=self.config.organization_id,
            name="Inactive filter",
            is_active=False,
            ignore_patterns="*.tmp",
        )
        backup_policy = BackupPolicy.objects.create(
            organization_id=self.config.organization_id,
            name="Inactive policy",
            is_active=False,
            error_handling={
                "enabled": True,
                "ignore_directory_read_errors": True,
                "ignore_file_read_errors": True,
                "ignore_unknown_entries": True,
            },
        )
        self.config.file_filter_rule_id = file_filter.id
        self.config.backup_policy_id = backup_policy.id
        self.config.save(update_fields=["file_filter_rule_id", "backup_policy_id", "updated_at"])

        snapshot = build_backup_runtime_policy(config=self.config)

        self.assertEqual(snapshot["file_filter"]["rule_id"], file_filter.id)
        self.assertFalse(snapshot["file_filter"]["active"])
        self.assertFalse(snapshot["file_filter"]["configured"])
        self.assertEqual(snapshot["backup_policy"]["policy_id"], backup_policy.id)
        self.assertFalse(snapshot["backup_policy"]["active"])
        self.assertFalse(snapshot["backup_policy"]["advanced_settings"]["enabled"])

    def test_policy_snapshot_preserves_missing_bound_ids(self):
        self.config.file_filter_rule_id = 901
        self.config.backup_policy_id = 902
        self.config.save(update_fields=["file_filter_rule_id", "backup_policy_id", "updated_at"])

        snapshot = build_backup_runtime_policy(config=self.config)

        self.assertEqual(snapshot["file_filter"]["rule_id"], 901)
        self.assertFalse(snapshot["file_filter"]["active"])
        self.assertEqual(snapshot["backup_policy"]["policy_id"], 902)
        self.assertFalse(snapshot["backup_policy"]["active"])

    def test_database_rejects_unknown_compression_level(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BackupConfig.objects.filter(id=self.config.id).update(compression_level="best")

    def test_database_allows_only_one_creating_snapshot_per_config(self):
        common = {
            "organization_id": self.config.organization_id,
            "source_type": self.config.source_type,
            "source_ref_id": self.config.source_ref_id,
            "backup_config_id": self.config.id,
            "repository_id": self.config.repository_id,
            "task_uuid": uuid.uuid4(),
            "status": BackupSourceSnapshot.Status.CREATING,
        }
        BackupSourceSnapshot.objects.create(
            **common,
            snapshot_uid="snapshot-active-1",
            idempotency_key="snapshot-active-1",
            task_id=501,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            BackupSourceSnapshot.objects.create(
                **{**common, "task_uuid": uuid.uuid4()},
                snapshot_uid="snapshot-active-2",
                idempotency_key="snapshot-active-2",
                task_id=502,
            )
