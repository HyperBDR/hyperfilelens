from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.iam.models import Organization
from apps.task.api.serializers.task import TaskSerializer
from apps.task.models import Task
from apps.task.services.interface import create_task


class TaskRecoveryChainTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            key="task-recovery-chain",
            name="Task Recovery Chain",
        )

    def _failed_task(
        self,
        *,
        organization: Organization | None = None,
        task_type: str = Task.Type.REPOSITORY_OPERATION,
        recovery_attempt: int = 0,
    ) -> Task:
        return Task.objects.create(
            organization_id=(organization or self.organization).id,
            task_type=task_type,
            display_name="Interrupted task",
            status=Task.Status.FAILED,
            recovery_attempt=recovery_attempt,
        )

    def _replacement(self, original: Task) -> Task:
        return create_task(
            organization_id=original.organization_id,
            task_type=original.task_type,
            display_name="Recovery replacement",
            trigger_type=Task.TriggerType.RETRY,
            normalize_trigger_type=False,
            replaces_task=original,
        )

    def test_replacement_increments_attempt_and_serializes_both_links(self):
        original = self._failed_task(recovery_attempt=2)

        replacement = self._replacement(original)

        self.assertEqual(replacement.recovery_attempt, 3)
        self.assertEqual(replacement.replaces_task_id, original.id)
        self.assertEqual(
            TaskSerializer(original).data["replacement_task_uuid"],
            str(replacement.task_uuid),
        )
        self.assertEqual(
            TaskSerializer(replacement).data["replaces_task_uuid"],
            str(original.task_uuid),
        )

    def test_replacement_requires_failed_task_with_same_org_and_type(self):
        pending = Task.objects.create(
            organization_id=self.organization.id,
            task_type=Task.Type.REPOSITORY_OPERATION,
            display_name="Still active",
        )
        other_organization = Organization.objects.create(
            key="other-task-recovery-chain",
            name="Other Task Recovery Chain",
        )

        invalid_replacements = (
            {
                "replaces_task": pending,
                "organization_id": self.organization.id,
                "task_type": Task.Type.REPOSITORY_OPERATION,
            },
            {
                "replaces_task": self._failed_task(organization=other_organization),
                "organization_id": self.organization.id,
                "task_type": Task.Type.REPOSITORY_OPERATION,
            },
            {
                "replaces_task": self._failed_task(task_type=Task.Type.BACKUP),
                "organization_id": self.organization.id,
                "task_type": Task.Type.REPOSITORY_OPERATION,
            },
        )
        for kwargs in invalid_replacements:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                create_task(
                    display_name="Invalid replacement",
                    **kwargs,
                )

    def test_task_can_have_only_one_replacement(self):
        original = self._failed_task()
        first = self._replacement(original)

        with self.assertRaises(ValidationError):
            self._replacement(original)

        self.assertEqual(Task.objects.filter(replaces_task=original).count(), 1)
        self.assertEqual(original.replacement_task.id, first.id)

    def test_recovery_attempt_is_derived_across_chain(self):
        current = self._failed_task()

        for expected_attempt in range(1, 4):
            current = self._replacement(current)
            self.assertEqual(current.recovery_attempt, expected_attempt)
            current.status = Task.Status.FAILED
            current.save(update_fields=["status", "updated_at"])
