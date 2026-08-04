from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.lens_bridge.models import LensGatewayLink
from apps.node.models import NodeToken
from apps.platform_ops.models import PlatformAuditLog


@override_settings(
    HFL_PLATFORM_OPS_ENABLED=True,
    FRONTEND_URL="https://console.example.com:11443",
)
class PlatformOpsLensGatewayEnrollmentTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="staff@test.com",
            email="staff@test.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)

    def _enroll(self):
        return self.client.post(
            "/api/v1/platform-ops/lens/gateways/enrollment",
            {"note": "platform gateway test"},
            format="json",
            HTTP_X_HFL_SITE_ROLE="ops",
        )

    def test_returns_tenant_origin_for_platform_gateway_install(self):
        response = self._enroll()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["api_base"], "https://console.example.com:11443")
        self.assertFalse(response.data["tls_verify"])
        self.assertEqual(response.data["org_key"], "__platform_lens__")
        self.assertEqual(
            response.data["gateway_scope"],
            LensGatewayLink.GatewayScope.PLATFORM,
        )

        token = NodeToken.objects.get(pk=response.data["token_id"])
        self.assertEqual(token.organization.key, "__platform_lens__")
        self.assertEqual(token.gateway_scope, LensGatewayLink.GatewayScope.PLATFORM)
        self.assertIsNotNone(token.expires_at)
        self.assertEqual(response.data["expires_at"], token.expires_at)
        self.assertTrue(
            PlatformAuditLog.objects.filter(
                action="gateway.enrollment.generate",
                target_id=str(token.id),
            ).exists()
        )

    @override_settings(HFL_INSECURE_TLS=False)
    def test_requires_tls_verification_for_strict_deployments(self):
        response = self._enroll()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["tls_verify"])

    @override_settings(FRONTEND_URL="https://console.example.com:11443/tenant")
    def test_rejects_invalid_frontend_url_without_creating_token(self):
        response = self._enroll()

        self.assertEqual(response.status_code, 503)
        self.assertIn("FRONTEND_URL", response.data["detail"])
        self.assertFalse(NodeToken.objects.exists())

    def test_uses_standard_batch_expiry_and_revoke(self):
        response = self.client.post(
            "/api/v1/platform-ops/lens/gateways/enrollment",
            {"ttl_seconds": 900},
            format="json",
            HTTP_X_HFL_SITE_ROLE="ops",
        )
        self.assertEqual(response.status_code, 201)
        token = NodeToken.objects.get(pk=response.data["token_id"])
        self.assertGreater(token.expires_at, timezone.now() + timedelta(hours=23))
        self.assertEqual(token.enrollment_mode, NodeToken.EnrollmentMode.CURRENT)

        revoked = self.client.delete(
            f"/api/v1/platform-ops/lens/gateways/enrollment/{token.id}",
            HTTP_X_HFL_SITE_ROLE="ops",
        )
        self.assertEqual(revoked.status_code, 204)
        token.refresh_from_db()
        self.assertFalse(token.is_active)
        self.assertTrue(
            PlatformAuditLog.objects.filter(
                action="gateway.enrollment.revoke",
                target_id=str(token.id),
            ).exists()
        )

    def test_audits_copy_without_storing_command(self):
        response = self._enroll()
        token_id = response.data["token_id"]

        copied = self.client.post(
            f"/api/v1/platform-ops/lens/gateways/enrollment/{token_id}/copied",
            format="json",
            HTTP_X_HFL_SITE_ROLE="ops",
        )
        self.assertEqual(copied.status_code, 204)
        audit = PlatformAuditLog.objects.get(
            action="gateway.enrollment.copy",
            target_id=str(token_id),
        )
        self.assertNotIn("token", audit.details)
        self.assertNotIn("command", audit.details)
