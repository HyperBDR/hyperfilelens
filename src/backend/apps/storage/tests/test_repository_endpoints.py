import importlib
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.storage.services.internal.repository_endpoints import (
    compact_s3_repository_endpoints,
    repository_control_endpoint,
    repository_data_endpoint,
    s3_endpoint_snapshot,
)


class RepositoryEndpointRoutingTests(SimpleTestCase):
    def test_data_plane_defaults_to_external_and_accepts_explicit_internal(self):
        snapshot = s3_endpoint_snapshot(
            external_endpoint="https://OSS-CN-HANGZHOU.ALIYUNCS.COM/",
            internal_endpoint="oss-cn-hangzhou-internal.aliyuncs.com",
            endpoint_type="internal",
        )

        self.assertEqual(snapshot["endpoint_type"], "internal")
        config = compact_s3_repository_endpoints(
            {},
            s3_platform="aliyun",
            external_endpoint=snapshot["external_endpoint"],
            internal_endpoint=snapshot["internal_endpoint"],
        )
        self.assertEqual(
            repository_data_endpoint(config),
            "oss-cn-hangzhou.aliyuncs.com",
        )
        self.assertEqual(
            repository_data_endpoint(config, endpoint_type="internal"),
            "oss-cn-hangzhou-internal.aliyuncs.com",
        )
        self.assertEqual(
            repository_control_endpoint(config),
            "oss-cn-hangzhou.aliyuncs.com",
        )

    def test_internal_data_plane_requires_a_distinct_internal_endpoint(self):
        with self.assertRaisesMessage(
            ValueError,
            "Internal Endpoint is not available for this repository.",
        ):
            repository_data_endpoint(
                {"endpoint": "s3.example.com"},
                endpoint_type="internal",
            )

    def test_equal_endpoints_are_normalized_to_external_selection(self):
        snapshot = s3_endpoint_snapshot(
            external_endpoint="obs.cn-north-1.myhuaweicloud.com",
            internal_endpoint="OBS.CN-NORTH-1.MYHUAWEICLOUD.COM.",
            endpoint_type="internal",
        )

        self.assertEqual(
            snapshot,
            {
                "endpoint_type": "external",
                "endpoint": "obs.cn-north-1.myhuaweicloud.com",
                "external_endpoint": "obs.cn-north-1.myhuaweicloud.com",
                "internal_endpoint": "obs.cn-north-1.myhuaweicloud.com",
            },
        )

    def test_legacy_repository_falls_back_to_selected_endpoint(self):
        legacy = {"endpoint": "https://legacy.example.com/"}

        self.assertEqual(repository_data_endpoint(legacy), "legacy.example.com")
        self.assertEqual(repository_control_endpoint(legacy), "legacy.example.com")

    def test_repository_config_is_compact_unless_managed_routes_are_distinct(self):
        equal = compact_s3_repository_endpoints(
            {"endpoint_type": "internal", "other": "value"},
            s3_platform="aws",
            external_endpoint="s3.amazonaws.com",
            internal_endpoint="S3.AMAZONAWS.COM.",
        )
        custom = compact_s3_repository_endpoints(
            {"external_endpoint": "ignored.example.com"},
            s3_platform="custom",
            external_endpoint="https://minio.example.com/",
            internal_endpoint="minio-internal.example.com",
        )
        distinct = compact_s3_repository_endpoints(
            {},
            s3_platform="aliyun",
            external_endpoint="oss-cn-hangzhou.aliyuncs.com",
            internal_endpoint="oss-cn-hangzhou-internal.aliyuncs.com",
        )

        self.assertEqual(equal, {"endpoint": "s3.amazonaws.com", "other": "value"})
        self.assertEqual(custom, {"endpoint": "minio.example.com"})
        self.assertEqual(
            distinct,
            {
                "endpoint": "oss-cn-hangzhou.aliyuncs.com",
                "external_endpoint": "oss-cn-hangzhou.aliyuncs.com",
                "internal_endpoint": "oss-cn-hangzhou-internal.aliyuncs.com",
            },
        )


class ProtectionRepositoryEndpointMigrationTests(SimpleTestCase):
    def test_migration_normalizes_legacy_null_snapshot_ids(self):
        migration = importlib.import_module(
            "apps.protection.migrations.0015_normalize_kopia_snapshot_ids"
        )
        legacy = SimpleNamespace(id=1, kopia_snapshot_id=" None ")
        valid = SimpleNamespace(id=2, kopia_snapshot_id="snapshot-2")
        queryset = Mock()
        queryset.iterator.return_value = [legacy, valid]
        manager = Mock()
        manager.exclude.return_value.only.return_value = queryset
        snapshot_directory = SimpleNamespace(objects=manager)
        apps = Mock()
        apps.get_model.return_value = snapshot_directory

        migration.normalize_legacy_kopia_snapshot_ids(apps, None)

        self.assertIsNone(legacy.kopia_snapshot_id)
        self.assertEqual(valid.kopia_snapshot_id, "snapshot-2")
        manager.bulk_update.assert_called_once_with(
            [legacy], ["kopia_snapshot_id"], batch_size=1000
        )

    def test_migration_preserves_distinct_legacy_internal_selection(self):
        migration = importlib.import_module(
            "apps.protection.migrations.0016_backup_config_repository_endpoint"
        )
        repository = SimpleNamespace(
            id=41,
            repo_type="s3",
            s3_platform="aliyun",
            config={
                "endpoint": "oss-cn-hangzhou-internal.aliyuncs.com",
                "endpoint_type": "internal",
                "external_endpoint": "oss-cn-hangzhou.aliyuncs.com",
                "internal_endpoint": "oss-cn-hangzhou-internal.aliyuncs.com",
            },
            save=Mock(),
        )
        config = SimpleNamespace(id=51, repository_id=repository.id, save=Mock())

        config_manager = Mock()
        config_manager.all.return_value.iterator.return_value = [config]
        repository_manager = Mock()
        repository_manager.filter.return_value = [repository]
        models = {
            ("protection", "BackupConfig"): SimpleNamespace(objects=config_manager),
            ("storage", "Repository"): SimpleNamespace(objects=repository_manager),
        }
        apps = Mock()
        apps.get_model.side_effect = lambda app_label, model_name: models[
            (app_label, model_name)
        ]

        migration.migrate_repository_endpoints(apps, None)

        self.assertEqual(config.repository_endpoint_type, "internal")
        config.save.assert_called_once_with(
            update_fields=["repository_endpoint_type"]
        )
        self.assertEqual(
            repository.config,
            {
                "endpoint": "oss-cn-hangzhou.aliyuncs.com",
                "external_endpoint": "oss-cn-hangzhou.aliyuncs.com",
                "internal_endpoint": "oss-cn-hangzhou-internal.aliyuncs.com",
            },
        )
        repository.save.assert_called_once_with(
            update_fields=["config", "updated_at"]
        )

    def test_migration_compacts_custom_and_equal_endpoint_repositories(self):
        migration = importlib.import_module(
            "apps.protection.migrations.0016_backup_config_repository_endpoint"
        )
        custom = SimpleNamespace(
            id=61,
            s3_platform="custom",
            config={
                "endpoint": "https://MINIO.EXAMPLE.COM/",
                "endpoint_type": "external",
                "external_endpoint": "minio.example.com",
                "internal_endpoint": "minio.example.com",
            },
            save=Mock(),
        )
        equal = SimpleNamespace(
            id=62,
            s3_platform="huaweicloud",
            config={
                "endpoint": "obs.cn-north-1.myhuaweicloud.com",
                "endpoint_type": "internal",
                "external_endpoint": "obs.cn-north-1.myhuaweicloud.com",
                "internal_endpoint": "OBS.CN-NORTH-1.MYHUAWEICLOUD.COM.",
            },
            save=Mock(),
        )

        config_manager = Mock()
        config_manager.all.return_value.iterator.return_value = []
        repository_manager = Mock()
        repository_manager.filter.return_value = [custom, equal]
        models = {
            ("protection", "BackupConfig"): SimpleNamespace(objects=config_manager),
            ("storage", "Repository"): SimpleNamespace(objects=repository_manager),
        }
        apps = Mock()
        apps.get_model.side_effect = lambda app_label, model_name: models[
            (app_label, model_name)
        ]

        migration.migrate_repository_endpoints(apps, None)

        self.assertEqual(custom.config, {"endpoint": "minio.example.com"})
        self.assertEqual(
            equal.config,
            {"endpoint": "obs.cn-north-1.myhuaweicloud.com"},
        )

    def test_migration_normalizes_legacy_huawei_provider_id(self):
        migration = importlib.import_module(
            "apps.protection.migrations.0016_backup_config_repository_endpoint"
        )
        repository = SimpleNamespace(
            id=64,
            s3_platform="huawei",
            config={
                "endpoint": "obs.cn-north-1.myhuaweicloud.com",
                "s3_platform": "huawei",
            },
            save=Mock(),
        )

        config_manager = Mock()
        config_manager.all.return_value.iterator.return_value = []
        repository_manager = Mock()
        repository_manager.filter.return_value = [repository]
        models = {
            ("protection", "BackupConfig"): SimpleNamespace(objects=config_manager),
            ("storage", "Repository"): SimpleNamespace(objects=repository_manager),
        }
        apps = Mock()
        apps.get_model.side_effect = lambda app_label, model_name: models[
            (app_label, model_name)
        ]

        migration.migrate_repository_endpoints(apps, None)

        self.assertEqual(repository.s3_platform, "huaweicloud")
        self.assertEqual(
            repository.config,
            {
                "endpoint": "obs.cn-north-1.myhuaweicloud.com",
                "s3_platform": "huaweicloud",
            },
        )
        repository.save.assert_called_once_with(
            update_fields=["config", "s3_platform", "updated_at"]
        )

    def test_migration_rejects_s3_repository_without_usable_endpoint(self):
        migration = importlib.import_module(
            "apps.protection.migrations.0016_backup_config_repository_endpoint"
        )
        repository = SimpleNamespace(
            id=63,
            s3_platform="custom",
            config={},
            save=Mock(),
        )

        config_manager = Mock()
        config_manager.all.return_value.iterator.return_value = []
        repository_manager = Mock()
        repository_manager.filter.return_value = [repository]
        models = {
            ("protection", "BackupConfig"): SimpleNamespace(objects=config_manager),
            ("storage", "Repository"): SimpleNamespace(objects=repository_manager),
        }
        apps = Mock()
        apps.get_model.side_effect = lambda app_label, model_name: models[
            (app_label, model_name)
        ]

        with self.assertRaisesMessage(
            RuntimeError,
            "S3 Repository 63 has no usable Endpoint.",
        ):
            migration.migrate_repository_endpoints(apps, None)

        repository.save.assert_not_called()
