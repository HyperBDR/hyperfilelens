"""Tests for optional node list pagination."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.services.registration_service import provision_registered_user_tenant
from apps.node.models import Node
from apps.node.models.base import NodeRole

User = get_user_model()


class NodeListPaginationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="node-page-user@test.local",
            email="node-page-user@test.local",
            password="Pass1234",
            is_active=True,
        )
        self.org, _ = provision_registered_user_tenant(self.user)
        self.client.force_authenticate(user=self.user)
        for idx in range(35):
            Node.objects.create(
                organization=self.org,
                name=f"agent-{idx:02d}",
                role=NodeRole.AGENT,
                ip_address=f"10.0.0.{idx + 1}",
            )

    def test_list_without_page_size_returns_all(self):
        response = self.client.get(
            reverse("node-list"),
            {"role": "agent"},
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 35)

    def test_list_with_page_size_returns_paginated_payload(self):
        response = self.client.get(
            reverse("node-list"),
            {"role": "agent", "page": 1, "page_size": 30},
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 35)
        self.assertEqual(len(response.data["results"]), 30)

        page_two = self.client.get(
            reverse("node-list"),
            {"role": "agent", "page": 2, "page_size": 30},
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(page_two.status_code, status.HTTP_200_OK)
        self.assertEqual(len(page_two.data["results"]), 5)

    def test_list_search_filters_by_name(self):
        response = self.client.get(
            reverse("node-list"),
            {"role": "agent", "search": "agent-03", "page": 1, "page_size": 30},
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "agent-03")

    def test_list_field_search_filters_only_selected_field(self):
        response = self.client.get(
            reverse("node-list"),
            {"role": "agent", "search": "10.0.0.1", "search_field": "name", "page": 1, "page_size": 30},
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

        by_ip = self.client.get(
            reverse("node-list"),
            {"role": "agent", "search": "10.0.0.1", "search_field": "ip", "page": 1, "page_size": 30},
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(by_ip.status_code, status.HTTP_200_OK)
        self.assertEqual(by_ip.data["count"], 11)
