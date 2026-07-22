from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.lens_bridge.models import LensGatewayLink
from apps.node.models import NodeToken


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
