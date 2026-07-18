"""Tests for deployment host registration and host-scoped monitoring."""

import uuid

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.monitor.models import DeploymentHost, SystemMetric
from apps.monitor.services.interface import (
    build_system_monitor_payload,
    collect_and_persist_sample,
    list_deployment_hosts,
)
from apps.monitor.services.internal.deployment_host import (
    _consolidate_duplicate_hosts,
    touch_local_deployment_host,
)


def _payload(response):
    data = response.data
    if isinstance(data, dict) and "data" in data and "code" in data:
        return data["data"]
    return data


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class DeploymentHostMonitorTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="staff@test.com",
            email="staff@test.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)
        self.client.defaults["HTTP_X_HFL_SITE_ROLE"] = "ops"
        self.org = Organization.objects.create(key="acme", name="Acme")
        Membership.objects.create(
            user=self.staff,
            organization=self.org,
            role=Membership.Role.OWNER,
        )

    def test_touch_local_deployment_host_registers_current_machine(self):
        host = touch_local_deployment_host()
        self.assertIsNotNone(host.id)
        self.assertTrue(host.hostname)
        self.assertIsNotNone(host.last_seen_at)

    def test_list_deployment_hosts_api(self):
        touch_local_deployment_host()
        response = self.client.get("/api/v1/platform-ops/monitoring/hosts")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertGreaterEqual(len(payload["items"]), 1)
        self.assertIn("hostname", payload["items"][0])
        self.assertIn("status", payload["items"][0])

    def test_monitoring_host_filters_by_host_id(self):
        local = touch_local_deployment_host()
        remote = DeploymentHost.objects.create(
            hostname="remote-host-01",
            platform="Linux-test",
            ip_address="10.0.0.2",
            last_seen_at=timezone.now(),
        )
        SystemMetric.objects.create(host=remote, cpu={"usage_percent": 42})

        response = self.client.get(
            "/api/v1/platform-ops/monitoring/host",
            {"hours": "1", "host_id": str(remote.id)},
        )
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertEqual(payload["host_id"], str(remote.id))
        self.assertEqual(payload["host"]["hostname"], remote.hostname)

        local_response = self.client.get(
            "/api/v1/platform-ops/monitoring/host",
            {"hours": "1", "host_id": str(local.id)},
        )
        self.assertEqual(local_response.status_code, 200)

    def test_monitoring_host_unknown_id_returns_404(self):
        response = self.client.get(
            "/api/v1/platform-ops/monitoring/host",
            {"hours": "1", "host_id": str(uuid.uuid4())},
        )
        self.assertEqual(response.status_code, 404)

    def test_build_system_monitor_payload_without_host_id_uses_local(self):
        local = touch_local_deployment_host()
        collect_and_persist_sample(host=local)
        since = timezone.now() - timezone.timedelta(hours=1)
        until = timezone.now()
        payload = build_system_monitor_payload(since=since, until=until)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["host_id"], str(local.id))
        self.assertGreaterEqual(len(payload["series"]), 1)

    def test_build_system_monitor_payload_is_read_only(self):
        local = touch_local_deployment_host()
        SystemMetric.objects.create(host=local, cpu={"usage_percent": 11})
        since = timezone.now() - timezone.timedelta(hours=1)
        until = timezone.now()
        before = SystemMetric.objects.filter(host=local).count()
        payload = build_system_monitor_payload(since=since, until=until, host_id=str(local.id))
        after = SystemMetric.objects.filter(host=local).count()
        self.assertIsNotNone(payload)
        self.assertEqual(before, after)
        self.assertEqual(len(payload["series"]), 1)

    def test_consolidates_duplicate_hosts_with_same_boot_time(self):
        boot = 1_700_000_000.0
        primary = DeploymentHost.objects.create(
            hostname="host-primary",
            name="wsl-dev",
            boot_time=boot,
            last_seen_at=timezone.now(),
        )
        duplicate = DeploymentHost.objects.create(
            hostname="2d938fe86830",
            name="2d938fe86830",
            boot_time=boot,
            last_seen_at=timezone.now() - timezone.timedelta(hours=1),
        )
        metric = SystemMetric.objects.create(host=duplicate, cpu={"usage_percent": 12})

        _consolidate_duplicate_hosts(primary)

        self.assertFalse(DeploymentHost.objects.filter(pk=duplicate.pk).exists())
        metric.refresh_from_db()
        self.assertEqual(metric.host_id, primary.id)
        self.assertEqual(DeploymentHost.objects.filter(boot_time=boot).count(), 1)

    def test_list_deployment_hosts_hides_long_offline_stale_rows(self):
        DeploymentHost.objects.create(
            hostname="legacy-wsl-key",
            name="legacy-offline-host",
            platform="Linux-test",
            last_seen_at=timezone.now() - timezone.timedelta(days=3),
        )
        touch_local_deployment_host()
        items = list_deployment_hosts()
        names = {item["name"] for item in items}
        self.assertNotIn("legacy-offline-host", names)
