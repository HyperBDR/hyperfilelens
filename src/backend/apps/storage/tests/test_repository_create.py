from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.iam.models import Membership, Organization
from apps.node.models import Node
from apps.storage.repositories.models import Credential, Repository, RepositoryTask
from apps.storage.services.internal.repository_create import (
    enqueue_repository_create_task,
    run_repository_create_task,
)
from apps.storage.services.internal.repository_errors import (
    REPOSITORY_ALREADY_EXISTS_CODE,
    RepositoryAlreadyExistsError,
)
from apps.storage.services.internal.repository_initializer import RepositoryInitializationError


class RepositoryCreateTaskTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            key="repository-create-org",
            name="Repository Create Org",
        )
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="repository-create@test.local",
            password="test-pass",
        )
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )

    def _s3_repository(self, *, name: str = "async-s3", status=Repository.Status.CREATING):
        credential = Credential.objects.create(
            organization_id=self.org.id,
            credential_type=Credential.Type.S3,
            metadata={"access_key_id": "AKIA_TEST"},
        )
        credential.set_secret_payload(
            {"secret_access_key": "secret", "kopia_password": "kopia-pass"}
        )
        credential.save()
        return Repository.objects.create(
            organization_id=self.org.id,
            name=name,
            repo_type=Repository.Type.S3,
            status=status,
            health=Repository.Health.OFFLINE,
            s3_platform=Repository.S3Platform.AWS,
            s3_bucket="async-bucket",
            credential_id=credential.id,
            config={
                "region": "us-east-1",
                "endpoint": "s3.amazonaws.com",
                "prefix": "kopia",
                "access_key_id": "AKIA_TEST",
            },
        )

    def _enqueue_create(self, repository, *, operation_type=RepositoryTask.OperationType.CREATE_REPOSITORY):
        return enqueue_repository_create_task(
            repository=repository,
            operation_type=operation_type,
            dispatch=False,
        )

    @mock.patch(
        "apps.storage.services.internal.repository_create.enqueue_repository_usage_refresh"
    )
    @mock.patch("apps.storage.services.internal.repository_create.initialize_s3_repository")
    def test_run_create_task_s3_success(self, initialize, _enqueue):
        repository = self._s3_repository()
        repository_task = self._enqueue_create(repository)

        result = run_repository_create_task(repository_task_id=repository_task.id)

        self.assertEqual(result["status"], "success")
        repository.refresh_from_db()
        self.assertEqual(repository.status, Repository.Status.CREATED)
        self.assertEqual(repository.health, Repository.Health.ONLINE)
        initialize.assert_called_once_with(repository)
        _enqueue.assert_called_once()

    @mock.patch("apps.storage.services.internal.repository_create.initialize_s3_repository")
    def test_run_create_task_s3_init_failure_keeps_row(self, initialize):
        initialize.side_effect = RepositoryInitializationError("S3 init failed")
        repository = self._s3_repository()
        repository_task = self._enqueue_create(repository)

        result = run_repository_create_task(repository_task_id=repository_task.id)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "REPOSITORY_S3_CREATE_FAILED")
        repository.refresh_from_db()
        self.assertEqual(repository.status, Repository.Status.CREATE_FAILED)
        self.assertEqual(repository.health, Repository.Health.OFFLINE)
        self.assertTrue(Repository.objects.filter(id=repository.id).exists())

    @mock.patch("apps.storage.services.internal.repository_create.initialize_s3_repository")
    def test_run_create_task_s3_already_exists_deletes_row(self, initialize):
        initialize.side_effect = RepositoryAlreadyExistsError("repository already exists")
        repository = self._s3_repository()
        credential_id = repository.credential_id
        repository_task = self._enqueue_create(repository)

        result = run_repository_create_task(repository_task_id=repository_task.id)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], REPOSITORY_ALREADY_EXISTS_CODE)
        self.assertFalse(Repository.objects.filter(id=repository.id).exists())
        self.assertFalse(Credential.objects.filter(id=credential_id).exists())

    @mock.patch(
        "apps.storage.services.internal.repository_create.enqueue_repository_usage_refresh"
    )
    @mock.patch(
        "apps.storage.services.internal.repository_create.initialize_proxy_nas_repository"
    )
    def test_run_repair_bind_already_exists_restores_unbound(self, initialize, _enqueue):
        proxy = Node.objects.create(
            organization=self.org,
            name="repair-proxy",
            role=Node.Role.PROXY,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.40",
        )
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name="repair-bind-nas",
            repo_type=Repository.Type.NAS,
            nas_protocol=Repository.NasProtocol.SMB,
            status=Repository.Status.CREATING,
            health=Repository.Health.OFFLINE,
            bind_node_type=Repository.BindNodeType.PROXY,
            bind_node_id=proxy.id,
            config={
                "server_address": "10.0.0.10",
                "share_path": "/backup",
                "proxy_mount_path": "/mnt/hfl/storage-repositories/repo-1-node-1",
            },
        )
        initialize.side_effect = RepositoryAlreadyExistsError("repository already exists")
        repository_task = self._enqueue_create(
            repository,
            operation_type=RepositoryTask.OperationType.REPAIR_BIND,
        )

        result = run_repository_create_task(repository_task_id=repository_task.id)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], REPOSITORY_ALREADY_EXISTS_CODE)
        repository.refresh_from_db()
        self.assertIsNone(repository.bind_node_type)
        self.assertIsNone(repository.bind_node_id)
        self.assertEqual(repository.status, Repository.Status.CREATED)
        self.assertEqual(repository.health, Repository.Health.UNVERIFIED)
        self.assertNotIn("proxy_mount_path", repository.config)
        initialize.assert_called_once()
