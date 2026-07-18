"""Tests for node lifecycle batch operation endpoints."""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.services.registration_service import provision_registered_user_tenant
from apps.node.models import Node
from apps.node.models.base import NodeRole

User = get_user_model()


class NodeOperationsApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ops-api@test.local",
            email="ops-api@test.local",
            password="test-pass",
            is_active=True,
        )
        self.org, _ = provision_registered_user_tenant(self.user)
        self.node = Node.objects.create(
            organization=self.org,
            name="agent-ops",
            role=NodeRole.AGENT,
            status=Node.Status.OFFLINE,
            version="1.0.0",
        )

    def test_preview_endpoint_accepts_trailing_slash(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("node-operations-preview"),
            data={"kind": "remove", "node_ids": [self.node.id]},
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["kind"], "remove")
        self.assertEqual(len(response.data["eligible"]), 1)
