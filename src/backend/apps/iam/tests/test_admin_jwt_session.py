from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework_simplejwt.tokens import AccessToken


class AdminJWTSessionMiddlewareTest(TestCase):
    def setUp(self):
        blacklist_patcher = patch(
            "apps.iam.auth.authentication.is_token_blacklisted",
            return_value=False,
        )
        blacklist_patcher.start()
        self.addCleanup(blacklist_patcher.stop)
        self.client = Client()
        self.staff = User.objects.create_user(
            username="staff@test.com",
            email="staff@test.com",
            password="Pass1234",
            is_staff=True,
        )

    def _set_access_cookie(self, user):
        self.client.cookies["access_token"] = str(AccessToken.for_user(user))

    def test_staff_jwt_creates_admin_session_on_ops_listener(self):
        self._set_access_cookie(self.staff)

        response = self.client.get("/admin/", HTTP_X_HFL_SITE_ROLE="ops")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.staff.pk)

    def test_tenant_listener_does_not_create_admin_session(self):
        self._set_access_cookie(self.staff)

        response = self.client.get("/admin/", HTTP_X_HFL_SITE_ROLE="tenant")

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_non_staff_jwt_does_not_create_admin_session(self):
        user = User.objects.create_user(
            username="user@test.com",
            email="user@test.com",
            password="Pass1234",
        )
        self._set_access_cookie(user)

        response = self.client.get("/admin/", HTTP_X_HFL_SITE_ROLE="ops")

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
