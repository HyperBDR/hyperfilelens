from subprocess import CompletedProcess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.storage.repositories.models import Repository
from apps.storage.services.internal.kopia_cli import (
    KopiaCliError,
    KopiaRepositoryAlreadyExistsError,
    _connection_fingerprint_file,
    _invalidate_changed_s3_connection,
    _s3_flags,
    create_s3_repository,
    run_maintenance,
)


class KopiaS3URLStyleCommandTests(SimpleTestCase):
    @patch("apps.storage.services.internal.kopia_cli._kopia_path", return_value="/usr/local/bin/kopia")
    @patch("apps.storage.services.internal.kopia_cli._kopia_supports_s3_url_style", return_value=True)
    def test_huawei_virtual_hosted_style_uses_patched_flag(self, _supports, _path):
        repository = Repository(
            repo_type=Repository.Type.S3,
            s3_platform=Repository.S3Platform.HUAWEI,
            s3_bucket="bucket",
            config={"endpoint": "obs.cn-north-5.myhuaweicloud.com"},
        )

        self.assertIn("--url-style=virtual-hosted", _s3_flags(repository))

    @patch("apps.storage.services.internal.kopia_cli._kopia_path", return_value="/usr/bin/kopia")
    @patch("apps.storage.services.internal.kopia_cli._kopia_supports_s3_url_style", return_value=False)
    def test_official_binary_rejects_virtual_hosted_requirement(self, _supports, _path):
        repository = Repository(
            repo_type=Repository.Type.S3,
            s3_platform=Repository.S3Platform.HUAWEI,
            s3_bucket="bucket",
            config={"s3_url_style": "virtual_hosted"},
        )

        with self.assertRaisesMessage(KopiaCliError, "does not support --url-style"):
            _s3_flags(repository)

    @patch(
        "apps.storage.services.internal.kopia_cli._s3_connection_fingerprint",
        return_value="new-fingerprint",
    )
    def test_changed_connection_fingerprint_invalidates_local_config(self, _fingerprint):
        repository = Repository(repo_type=Repository.Type.S3)
        with TemporaryDirectory() as temporary:
            config_file = Path(temporary) / "repository.config"
            config_file.write_text("configured", encoding="utf-8")
            _connection_fingerprint_file(config_file).write_text(
                "old-fingerprint\n", encoding="utf-8"
            )

            _invalidate_changed_s3_connection(repository, config_file)

            self.assertFalse(config_file.exists())


class KopiaRepositoryCreateCommandTests(SimpleTestCase):
    @patch("apps.storage.services.internal.kopia_cli._run_repository_command")
    def test_existing_repository_is_rejected_without_connect(self, run_command):
        run_command.return_value = CompletedProcess(
            [],
            1,
            stdout="",
            stderr="repository already exists in the provided storage",
        )
        repository = Repository(
            id=52,
            name="S3 repository",
            repo_type=Repository.Type.S3,
            s3_bucket="bucket",
            config={"endpoint": "s3.example.test", "prefix": "repo/"},
        )

        with self.assertRaises(KopiaRepositoryAlreadyExistsError):
            create_s3_repository(repository)

        self.assertEqual(run_command.call_count, 1)
        self.assertEqual(
            run_command.call_args.args[1][:3],
            ["repository", "create", "s3"],
        )


class KopiaMaintenanceCommandTests(SimpleTestCase):
    @patch("apps.storage.services.internal.kopia_cli._run_repository_command")
    def test_uses_dedicated_config_and_set_client_identity(self, run_command):
        run_command.return_value = CompletedProcess([], 0, stdout="", stderr="")
        repository = Repository(
            id=52,
            name="S3 repository",
            repo_type=Repository.Type.S3,
            s3_bucket="bucket",
            config={"endpoint": "s3.example.test", "prefix": "repo/"},
        )

        run_maintenance(
            repository,
            full=False,
            owner_identity="hfl-maintenance@controller",
            timeout_seconds=300,
        )

        commands = [call.args[1] for call in run_command.call_args_list]
        self.assertEqual(commands[0][:3], ["repository", "connect", "s3"])
        self.assertEqual(
            commands[1],
            [
                "repository",
                "set-client",
                "--username=hfl-maintenance",
                "--hostname=controller",
            ],
        )
        self.assertEqual(
            commands[2],
            [
                "maintenance",
                "set",
                "--owner=hfl-maintenance@controller",
                "--enable-quick=false",
                "--enable-full=false",
            ],
        )
        self.assertEqual(commands[3], ["maintenance", "run"])
        self.assertIn("--region=us-east-1", commands[0])
        self.assertFalse(any("override-username" in arg for command in commands for arg in command))
        config_files = [call.kwargs["config_file"] for call in run_command.call_args_list]
        self.assertEqual(len(set(config_files)), 1)
        self.assertEqual(config_files[0].name, "maintenance.repository.config")

    @patch("apps.storage.services.internal.kopia_cli.time.sleep")
    @patch("apps.storage.services.internal.kopia_cli._run_repository_command")
    def test_retries_failed_repository_connection(self, run_command, sleep):
        failed = CompletedProcess([], 1, stdout="", stderr="Connection closed by foreign host. Retry again.")
        succeeded = CompletedProcess([], 0, stdout="", stderr="")
        run_command.side_effect = [failed, failed, succeeded, succeeded, succeeded, succeeded]
        repository = Repository(
            id=52,
            name="S3 repository",
            repo_type=Repository.Type.S3,
            s3_bucket="bucket",
            config={"endpoint": "minio.example.test", "prefix": "repo/"},
        )

        run_maintenance(
            repository,
            full=False,
            owner_identity="hfl-maintenance@controller",
            timeout_seconds=300,
        )

        commands = [call.args[1] for call in run_command.call_args_list]
        self.assertEqual(commands[0][:3], ["repository", "connect", "s3"])
        self.assertEqual(commands[1], ["repository", "status"])
        self.assertEqual(commands[2][:3], ["repository", "connect", "s3"])
        sleep.assert_called_once_with(1)
