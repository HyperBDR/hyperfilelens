from subprocess import CompletedProcess
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.storage.repositories.models import Repository
from apps.storage.services.internal.kopia_cli import (
    KopiaRepositoryAlreadyExistsError,
    create_s3_repository,
    run_maintenance,
)


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
