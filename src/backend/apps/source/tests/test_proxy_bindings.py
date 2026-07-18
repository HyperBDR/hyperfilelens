"""Tests for source-side Proxy binding guard (NAS / NFS / CIFS)."""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.source.models import SourceResource
from apps.source.constants import ResourceType


class SourceProxyBindingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="source-proxy-bind@test.local",
            email="source-proxy-bind@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="source-proxy-bind-org", name="Source Proxy Bind Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )
        self.client.force_authenticate(user=self.user)
        self.proxy_a = Node.objects.create(
            organization=self.org,
            name="proxy-a",
            role=NodeRole.PROXY,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.41",
        )
        self.proxy_b = Node.objects.create(
            organization=self.org,
            name="proxy-b",
            role=NodeRole.PROXY,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.42",
        )

    def _headers(self):
        return {"HTTP_X_ORG_KEY": self.org.key}

    def test_source_nas_cannot_unbind_proxy(self):
        resource = SourceResource.objects.create(
            organization=self.org,
            name="source-nas",
            resource_type=ResourceType.NAS,
            bound_node=self.proxy_a,
            config={"server": "10.0.0.20", "export_path": "/export"},
        )
        response = self.client.patch(
            f"/api/v1/source/resources/{resource.id}/",
            {"bound_node": None},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        resource.refresh_from_db()
        self.assertEqual(resource.bound_node_id, self.proxy_a.id)

    @mock.patch("apps.source.services.interface.schedule_remount_after_proxy_change")
    def test_source_nas_can_replace_proxy(self, mock_schedule):
        resource = SourceResource.objects.create(
            organization=self.org,
            name="source-nas",
            resource_type=ResourceType.NFS,
            bound_node=self.proxy_a,
            config={"server": "10.0.0.20", "export_path": "/export"},
        )
        response = self.client.patch(
            f"/api/v1/source/resources/{resource.id}/",
            {"bound_node_id": self.proxy_b.id},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        mock_schedule.assert_called_once()
        resource.refresh_from_db()
        self.assertEqual(resource.bound_node_id, self.proxy_b.id)

    @mock.patch("apps.source.services.interface.schedule_remount_after_proxy_change")
    def test_source_nas_replace_proxy_schedules_remount(self, mock_schedule):
        resource = SourceResource.objects.create(
            organization=self.org,
            name="source-nas-remount-fail",
            resource_type=ResourceType.NFS,
            bound_node=self.proxy_a,
            config={"server": "10.0.0.20", "export_path": "/export"},
        )
        response = self.client.patch(
            f"/api/v1/source/resources/{resource.id}/",
            {"bound_node_id": self.proxy_b.id},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        resource.refresh_from_db()
        self.assertEqual(resource.bound_node_id, self.proxy_b.id)
        mock_schedule.assert_called_once()

    def test_unbind_action_rejected_for_source_nas(self):
        resource = SourceResource.objects.create(
            organization=self.org,
            name="source-nas",
            resource_type=ResourceType.CIFS,
            bound_node=self.proxy_a,
            config={"server": "10.0.0.20", "share": "/share"},
        )
        # The view exposes unbind_node for the writer route; emulate the
        # service directly to verify the guard.
        from apps.source.services import unbind_node
        result = unbind_node(resource=resource)
        self.assertFalse(result["success"])
        resource.refresh_from_db()
        self.assertEqual(resource.bound_node_id, self.proxy_a.id)
