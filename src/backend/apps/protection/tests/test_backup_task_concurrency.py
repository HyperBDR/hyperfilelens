from __future__ import annotations

import queue
import threading
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.iam.models import Organization
from apps.node.models import Node
from apps.protection.models import BackupConfig, BackupConfigDirectory, BackupSourceSnapshot
from apps.protection.services.backup_task import start_backup_tasks
from apps.source.models import SourceBackupPipelineEntry
from apps.storage.repositories.models import Repository
from apps.task.models import Task


class BackupTaskConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if not connection.features.has_select_for_update:
            self.skipTest("Database backend does not support row-level locking.")
        self.org = Organization.objects.create(
            key="backup-concurrency-org",
            name="Backup Concurrency Org",
        )
        self.agent = Node.objects.create(
            organization=self.org,
            name="backup-concurrency-agent",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.71",
        )
        self.repository = Repository.objects.create(
            organization_id=self.org.id,
            name="backup-concurrency-repo",
            repo_type=Repository.Type.S3,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            s3_platform=Repository.S3Platform.CUSTOM,
            s3_bucket="backup-concurrency-bucket",
            config={
                "endpoint": "s3.example.internal:9000",
                "region": "cn-test-1",
                "prefix": "kopia/concurrency",
                "access_key_id": "ak-test",
                "secret_access_key": "sk-test",
                "kopia_password": "repo-password",
                "use_tls": False,
            },
        )
        self.config = BackupConfig.objects.create(
            organization_id=self.org.id,
            name="Concurrent backup config",
            source_type="agent",
            source_ref_id=self.agent.id,
            repository_id=self.repository.id,
            compression_level=BackupConfig.CompressionLevel.BALANCED,
        )
        BackupConfigDirectory.objects.create(
            organization_id=self.org.id,
            backup_config=self.config,
            path="/data/concurrent",
            sort_order=0,
        )
        SourceBackupPipelineEntry.objects.create(
            organization=self.org,
            source_kind="agent",
            ref_id=self.agent.id,
            step=3,
        )

    def test_simultaneous_starts_create_one_active_backup(self):
        barrier = threading.Barrier(2)
        outcomes: queue.Queue[dict] = queue.Queue()
        errors: queue.Queue[BaseException] = queue.Queue()

        def start(idempotency_key: str) -> None:
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                outcomes.put(
                    start_backup_tasks(
                        organization_id=self.org.id,
                        source_ids=[f"agent:{self.agent.id}"],
                        trigger_type="manual",
                        idempotency_key=idempotency_key,
                    )
                )
            except BaseException as exc:  # pragma: no cover - surfaced in the main test thread
                errors.put(exc)
            finally:
                close_old_connections()

        with patch("apps.protection.services.backup_task._queue_backup_execution"):
            threads = [
                threading.Thread(target=start, args=("concurrent-a",)),
                threading.Thread(target=start, args=("concurrent-b",)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

        if not errors.empty():
            raise errors.get()
        self.assertEqual(outcomes.qsize(), 2)
        statuses = sorted(outcomes.get()["results"][0]["status"] for _ in range(2))
        self.assertEqual(statuses, ["conflict", "created"])
        self.assertEqual(Task.objects.filter(task_type=Task.Type.BACKUP).count(), 1)
        self.assertEqual(
            BackupSourceSnapshot.objects.filter(status=BackupSourceSnapshot.Status.CREATING).count(),
            1,
        )
