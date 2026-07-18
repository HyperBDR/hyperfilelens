"""Audit service facade tests."""

from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.audit.constants import AuditAction, AuditTargetType
from apps.audit.models import AuditLog
from apps.audit.selectors.interface import list_audit_logs
from apps.audit.services.interface import write_audit_log
from apps.iam.models import Organization


class AuditServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="audit-svc-org", name="Audit Svc Org")
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="audit-svc@test.local",
            email="audit-svc@test.local",
        )

    def test_write_and_list_via_facades(self):
        log = write_audit_log(
            organization=self.org,
            user=self.user,
            action=AuditAction.TASK_FINISH,
            target_type=AuditTargetType.TASK,
            target_id="99",
            correlation_id="corr-1",
        )
        self.assertEqual(log.action, AuditAction.TASK_FINISH)

        rows = list_audit_logs(org_key=self.org.key, action=AuditAction.TASK_FINISH)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().target_id, "99")

    def test_list_supports_datetime_bounds(self):
        old_log = write_audit_log(
            organization=self.org,
            user=self.user,
            action=AuditAction.TASK_CREATE,
            target_type=AuditTargetType.TASK,
            target_id="old",
        )
        matched_log = write_audit_log(
            organization=self.org,
            user=self.user,
            action=AuditAction.TASK_FINISH,
            target_type=AuditTargetType.TASK,
            target_id="matched",
        )
        new_log = write_audit_log(
            organization=self.org,
            user=self.user,
            action=AuditAction.TASK_CREATE,
            target_type=AuditTargetType.TASK,
            target_id="new",
        )
        AuditLog.objects.filter(id=old_log.id).update(
            created_at=timezone.make_aware(datetime(2026, 6, 29, 9, 0))
        )
        AuditLog.objects.filter(id=matched_log.id).update(
            created_at=timezone.make_aware(datetime(2026, 6, 29, 10, 30))
        )
        AuditLog.objects.filter(id=new_log.id).update(
            created_at=timezone.make_aware(datetime(2026, 6, 29, 12, 0))
        )

        rows = list_audit_logs(
            org_key=self.org.key,
            start_date="2026-06-29T10:00:00Z",
            end_date="2026-06-29T11:00:00Z",
        )

        self.assertEqual(list(rows.values_list("target_id", flat=True)), ["matched"])

    def test_list_keeps_date_bound_compatibility(self):
        log = write_audit_log(
            organization=self.org,
            user=self.user,
            action=AuditAction.TASK_FINISH,
            target_type=AuditTargetType.TASK,
            target_id="same-day",
        )
        AuditLog.objects.filter(id=log.id).update(
            created_at=timezone.make_aware(datetime(2026, 6, 29, 23, 59))
        )

        rows = list_audit_logs(
            org_key=self.org.key,
            start_date="2026-06-29",
            end_date="2026-06-29",
        )

        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().target_id, "same-day")
