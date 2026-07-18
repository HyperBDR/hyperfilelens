from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsUsersApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.defaults["HTTP_X_HFL_SITE_ROLE"] = "ops"
        self.staff = User.objects.create_user(
            username="staff@test.com",
            email="staff@test.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)
        self.org = Organization.objects.create(key="acme", name="Acme")
        self.member = User.objects.create_user(
            username="member@test.com",
            email="member@test.com",
            password="Pass1234",
        )
        Membership.objects.create(
            user=self.member,
            organization=self.org,
            role=Membership.Role.OWNER,
        )

    def test_list_users(self):
        response = self.client.get("/api/v1/platform-ops/users")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["count"], 2)

    def test_create_and_reset_password(self):
        create_resp = self.client.post(
            "/api/v1/platform-ops/users",
            {
                "email": "new@test.com",
                "password": "Pass1234",
                "is_active": True,
                "is_staff": False,
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201)
        user_id = create_resp.data["id"]

        reset_resp = self.client.post(
            f"/api/v1/platform-ops/users/{user_id}/reset-password",
            {"password": "Newpass1234"},
            format="json",
        )
        self.assertEqual(reset_resp.status_code, 200)

        target = User.objects.get(pk=user_id)
        self.assertTrue(target.check_password("Newpass1234"))

    def test_user_detail_includes_memberships(self):
        response = self.client.get(f"/api/v1/platform-ops/users/{self.member.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["memberships"]), 1)
        self.assertEqual(response.data["memberships"][0]["organization_key"], "acme")

    def test_response_omits_is_superuser(self):
        response = self.client.get(f"/api/v1/platform-ops/users/{self.member.pk}")
        self.assertNotIn("is_superuser", response.data)

    def test_create_staff_syncs_superuser(self):
        create_resp = self.client.post(
            "/api/v1/platform-ops/users",
            {
                "email": "ops@test.com",
                "password": "Pass1234",
                "is_staff": True,
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201)
        self.assertNotIn("is_superuser", create_resp.data)
        user = User.objects.get(email="ops@test.com")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_update_staff_syncs_superuser(self):
        user = User.objects.create_user(
            username="toggle@test.com",
            email="toggle@test.com",
            password="Pass1234",
            is_staff=True,
            is_superuser=True,
        )
        patch_resp = self.client.patch(
            f"/api/v1/platform-ops/users/{user.pk}",
            {"is_staff": False},
            format="json",
        )
        self.assertEqual(patch_resp.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_delete_user(self):
        user = User.objects.create_user(
            username="delete@test.com",
            email="delete@test.com",
            password="Pass1234",
        )
        response = self.client.delete(f"/api/v1/platform-ops/users/{user.pk}")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_cannot_delete_self(self):
        response = self.client.delete(f"/api/v1/platform-ops/users/{self.staff.pk}")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(pk=self.staff.pk).exists())
