"""Host smoke: create-path quota helpers + error code contract."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.iam.models import Membership, Organization
from apps.subscription.services.interface import (
    enforce_license_quota,
    enforce_node_role_quota,
    enforce_repository_type_quota,
)
from common.extension_spi import (
    clear_providers_for_tests,
    register_quota_provider,
    restore_providers_for_tests,
)


class _BlockingProvider:
    def check_quota(self, organization, resource_type, additional=1):
        from common.errors import AppError

        raise AppError(
            code="SUBSCRIPTION.QUOTA_EXCEEDED",
            status=403,
            title="blocked",
            diagnostic="blocked",
            meta={"quota_type": resource_type},
        )


class HostQuotaFacadeTests(TestCase):
    def setUp(self):
        self._spi_previous = clear_providers_for_tests()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="hq@test.local",
            email="hq@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="hq-org", name="HQ Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.OWNER,
        )

    def tearDown(self):
        restore_providers_for_tests(self._spi_previous)

    def test_helpers_noop_without_provider(self):
        self.assertIsNone(enforce_license_quota(self.org, "max_users", additional=1))
        self.assertIsNone(enforce_node_role_quota(organization=self.org, role="agent"))
        self.assertIsNone(enforce_repository_type_quota(organization=self.org, repo_type="s3"))

    def test_helpers_delegate_to_provider(self):
        register_quota_provider(_BlockingProvider())
        from common.errors import AppError

        with self.assertRaises(AppError) as ctx:
            enforce_license_quota(self.org, "max_users", additional=1)
        self.assertEqual(ctx.exception.code, "SUBSCRIPTION.QUOTA_EXCEEDED")
