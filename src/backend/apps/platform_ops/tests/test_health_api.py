from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.alert.constants import AlertSeverity, AlertStatus, AlertType, ResourceType
from apps.alert.models import AlertRecord
from apps.iam.models import Membership, Organization
from apps.monitor.services.interface import collect_and_persist_sample
from apps.notification.constants import ChannelType
from apps.notification.models import NotificationChannel, NotificationDelivery
from apps.task.models import Task


def _payload(response):
    data = response.data
    if isinstance(data, dict) and "data" in data and "code" in data:
        return data["data"]
    return data


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsMonitoringApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.defaults["HTTP_X_HFL_SITE_ROLE"] = "ops"
        self.staff = User.objects.create_user(
            username="staff@test.com",
            email="staff@test.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)
        self.org = Organization.objects.create(key="acme", name="Acme")
        Membership.objects.create(
            user=self.staff,
            organization=self.org,
            role=Membership.Role.OWNER,
        )

    def test_overview_ok(self):
        health = {
            "api": {"status": "ok"},
            "database": {"status": "ok", "latency_ms": 2},
            "redis": {"status": "ok", "latency_ms": 1},
            "celery": {"status": "ok", "worker_count": 1, "active_tasks": 0},
            "checked_at": "2026-07-22T00:00:00Z",
        }
        lens = {"configured": True, "reachable": True, "authenticated": True}
        with (
            patch(
                "apps.platform_ops.selectors.internal.overview.system_health_payload",
                return_value=health,
            ),
            patch(
                "apps.platform_ops.selectors.internal.overview.sl_client.ping",
                return_value=lens,
            ),
        ):
            response = self.client.get("/api/v1/platform-ops/", {"hours": "168"})
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("metrics", payload)
        self.assertEqual(payload["range_hours"], 168)
        self.assertEqual(payload["system_health"]["overall_status"], "healthy")
        self.assertEqual(len(payload["system_health"]["services"]), 5)
        self.assertEqual(len(payload["activity_series"]), 14)
        self.assertIn("repositories_at_risk", payload["metrics"])
        self.assertIn("ai_success_rate", payload["metrics"])

    def test_monitoring_tasks_ok(self):
        response = self.client.get("/api/v1/platform-ops/monitoring/tasks")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("results", payload)
        self.assertIn("stats", payload)

    def test_monitoring_incident_actions(self):
        incident = AlertRecord.objects.create(
            organization=self.org,
            type=AlertType.SYSTEM,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.FIRING,
            resource_type=ResourceType.SYSTEM_SERVICE,
            resource_name="database",
            title="Database unavailable",
            message="Health check failed",
            fingerprint="system:database",
            first_triggered_at=timezone.now(),
            last_triggered_at=timezone.now(),
        )
        response = self.client.get("/api/v1/platform-ops/monitoring/alerts")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertEqual(payload["stats"]["firing"], 1)

        response = self.client.post(
            f"/api/v1/platform-ops/monitoring/alerts/{incident.id}/acknowledge",
            {"note": "Investigating"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        incident.refresh_from_db()
        self.assertEqual(incident.status, AlertStatus.ACKNOWLEDGED)
        self.assertEqual(incident.metadata["acknowledge_note"], "Investigating")

    def test_monitoring_task_cancel_and_retry(self):
        task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Backup",
            status=Task.Status.RUNNING,
            started_at=timezone.now(),
        )
        response = self.client.post(
            f"/api/v1/platform-ops/monitoring/tasks/{task.task_uuid}/cancel",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.CANCELLED)

        response = self.client.post(
            f"/api/v1/platform-ops/monitoring/tasks/{task.task_uuid}/retry",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.PENDING)
        self.assertEqual(task.retry_count, 1)

    def test_monitoring_notifications_ok(self):
        channel = NotificationChannel.objects.create(
            organization=self.org,
            name="Operations Email",
            channel_type=ChannelType.EMAIL,
            config={"recipients": ["ops@example.com"]},
        )
        delivery = NotificationDelivery.objects.create(
            organization=self.org,
            channel=channel,
            event_type="alert.firing",
            status=NotificationDelivery.Status.FAILED,
            error="SMTP timeout",
            payload={"recipient": "operator@example.com", "token": "secret-token"},
        )
        response = self.client.get("/api/v1/platform-ops/monitoring/notifications")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["stats"]["failed"], 1)
        self.assertEqual(payload["results"][0]["channel_type"], ChannelType.EMAIL)
        self.assertEqual(payload["results"][0]["payload"]["recipient"], "op***@example.com")
        self.assertEqual(payload["results"][0]["payload"]["token"], "••••••••")

        def deliver(*, delivery):
            delivery.status = NotificationDelivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.save(update_fields=["status", "sent_at"])
            return SimpleNamespace(ok=True)

        with patch(
            "apps.platform_ops.api.views.monitoring.attempt_delivery",
            side_effect=deliver,
        ):
            response = self.client.post(
                f"/api/v1/platform-ops/monitoring/notifications/{delivery.id}/retry",
                {},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)

    def test_platform_environment_ok(self):
        response = self.client.get("/api/v1/platform-ops/platform/settings/environment")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("effective", payload)
        self.assertIn("health", payload)

    def test_platform_agent_releases_ok(self):
        response = self.client.get("/api/v1/platform-ops/platform/agent-releases")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("results", payload)
        self.assertIn("count", payload)
        self.assertIn("bootstrap", payload)
        self.assertIn("active_source", payload["bootstrap"])

    def test_platform_notification_channels_ok(self):
        response = self.client.get("/api/v1/platform-ops/platform/notification-channels")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("results", payload)
        self.assertIn("count", payload)

    def test_monitoring_host_ok(self):
        collect_and_persist_sample()
        response = self.client.get("/api/v1/platform-ops/monitoring/host", {"hours": "1"})
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("host", payload)
        self.assertIn("series", payload)
        self.assertIn("current", payload)

    def test_system_audit_ok(self):
        response = self.client.get("/api/v1/platform-ops/system/audit")
        self.assertEqual(response.status_code, 200)
