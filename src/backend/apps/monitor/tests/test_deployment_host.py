"""Deployment host registration and host-scoped monitoring (Host services).

Platform Ops HTTP surfaces (``/api/v1/platform-ops/monitoring/hosts|host``)
live on the commercial extension. Community empty socket must not expose them;
API behavior is covered in hyperfilelens-ee.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
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
from common.extension_loader import extensions_enabled


class DeploymentHostServiceTests(TestCase):
    def test_touch_local_deployment_host_registers_current_machine(self):
        host = touch_local_deployment_host()
        self.assertIsNotNone(host.id)
        self.assertTrue(host.hostname)
        self.assertIsNotNone(host.last_seen_at)

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
        payload = build_system_monitor_payload(
            since=since, until=until, host_id=str(local.id)
        )
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


class DeploymentHostPlatformOpsCommunityTests(TestCase):
    """Live URLconf: Community empty socket has no Platform Ops host monitor routes."""

    def setUp(self):
        if extensions_enabled():
            self.skipTest(
                "live URLconf has extension routes; see hyperfilelens-ee platform_ops tests"
            )
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

    def test_monitoring_hosts_unavailable_without_extension(self):
        response = self.client.get("/api/v1/platform-ops/monitoring/hosts")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_monitoring_host_unavailable_without_extension(self):
        response = self.client.get(
            "/api/v1/platform-ops/monitoring/host",
            {"hours": "1"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
