"""Usage statistics tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.iam.models import Membership, Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.subscription.services.internal.usage import collect_usage_stats


class UsageStatsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="usage@test.local",
            email="usage@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="usage-test-org", name="Usage Test Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )

    def test_collect_usage_counts_nodes_by_role(self):
        Node.objects.create(
            organization=self.org,
            name="agent-1",
            role=NodeRole.AGENT,
            status="online",
        )
        Node.objects.create(
            organization=self.org,
            name="proxy-1",
            role=NodeRole.PROXY,
            status="online",
        )
        Node.objects.create(
            organization=self.org,
            name="gateway-1",
            role=NodeRole.GATEWAY,
            status="online",
        )

        usage = collect_usage_stats(organization_id=self.org.id)

        self.assertEqual(usage["nodes_count"], 3)
        self.assertEqual(usage["agents_count"], 1)
        self.assertEqual(usage["proxies_count"], 1)
        self.assertEqual(usage["gateways_count"], 1)
