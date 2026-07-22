from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.iam.profile_models import Profile


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
        self.assertGreaterEqual(response.data["stats"]["active"], 2)
        member_row = next(
            row for row in response.data["results"] if row["id"] == self.member.pk
        )
        self.assertEqual(member_row["account_type"], "customer")
        self.assertEqual(member_row["organization"]["key"], "acme")

    def test_list_users_supports_account_filters_and_organization_search(self):
        customer_response = self.client.get(
            "/api/v1/platform-ops/users",
            {"account_type": "customer", "search": "acme"},
        )
        self.assertEqual(customer_response.status_code, 200)
        self.assertEqual(customer_response.data["count"], 1)
        self.assertEqual(customer_response.data["results"][0]["id"], self.member.pk)

        admin_response = self.client.get(
            "/api/v1/platform-ops/users",
            {"account_type": "administrator"},
        )
        self.assertEqual(admin_response.status_code, 200)
        self.assertTrue(
            all(row["account_type"] == "administrator" for row in admin_response.data["results"])
        )

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
        self.assertEqual(len(create_resp.data["memberships"]), 1)
        self.assertEqual(
            create_resp.data["memberships"][0]["role"],
            Membership.Role.OWNER,
        )

        membership = Membership.objects.select_related("organization").get(
            user_id=user_id,
        )
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.organization.name, "new@test.com")
        self.assertTrue(membership.is_active)

        profile = Profile.objects.get(user_id=user_id)
        self.assertTrue(profile.registration_completed)

        reset_resp = self.client.post(
            f"/api/v1/platform-ops/users/{user_id}/reset-password",
            {"password": "Newpass1234"},
            format="json",
        )
        self.assertEqual(reset_resp.status_code, 200)

        target = User.objects.get(pk=user_id)
        self.assertTrue(target.check_password("Newpass1234"))

    def test_create_accepts_customer_organization_name(self):
        response = self.client.post(
            "/api/v1/platform-ops/users",
            {
                "email": "named@test.com",
                "password": "Pass1234",
                "organization_name": "Named Customer",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["organization"]["name"], "Named Customer")
        membership = Membership.objects.select_related("organization").get(
            user_id=response.data["id"],
        )
        self.assertEqual(membership.organization.name, "Named Customer")

    def test_created_tenant_user_can_reach_org_selection(self):
        create_resp = self.client.post(
            "/api/v1/platform-ops/users",
            {
                "email": "login-ready@test.com",
                "password": "Pass1234",
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201)

        anonymous = APIClient()
        login_resp = anonymous.post(
            "/api/v1/auth/email-login",
            {
                "email": "login-ready@test.com",
                "password": "Pass1234",
            },
            format="json",
        )

        self.assertEqual(login_resp.status_code, 200)
        self.assertEqual(len(login_resp.data["data"]["available_orgs"]), 1)
        self.assertEqual(
            login_resp.data["data"]["available_orgs"][0]["role"],
            Membership.Role.OWNER,
        )

    @patch(
        "apps.lens_bridge.services.chat_user_provisioning.enqueue_sl_chat_user_provision"
    )
    def test_create_tenant_user_queues_sourcelens_provision(self, mock_enqueue):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/platform-ops/users",
                {
                    "email": "sourcelens@test.com",
                    "password": "Pass1234",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="sourcelens@test.com")
        mock_enqueue.assert_called_once_with(user_id=user.pk)

    def test_create_rejects_duplicate_email(self):
        response = self.client.post(
            "/api/v1/platform-ops/users",
            {
                "email": self.member.email.upper(),
                "password": "Pass1234",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            User.objects.filter(email__iexact=self.member.email).count(),
            1,
        )

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
        self.assertFalse(Membership.objects.filter(user=user).exists())

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
        self.assertTrue(
            Membership.objects.filter(
                user=user,
                role=Membership.Role.OWNER,
                is_active=True,
            ).exists()
        )

    def test_customer_with_organization_cannot_be_promoted_to_platform_admin(self):
        response = self.client.patch(
            f"/api/v1/platform-ops/users/{self.member.pk}",
            {"is_staff": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_staff)

    def test_staff_cannot_remove_own_console_access(self):
        deactivate = self.client.patch(
            f"/api/v1/platform-ops/users/{self.staff.pk}",
            {"is_active": False},
            format="json",
        )
        demote = self.client.patch(
            f"/api/v1/platform-ops/users/{self.staff.pk}",
            {"is_staff": False},
            format="json",
        )

        self.assertEqual(deactivate.status_code, 400)
        self.assertEqual(demote.status_code, 400)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)
        self.assertTrue(self.staff.is_staff)

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

    def test_cannot_delete_organization_owner(self):
        response = self.client.delete(
            f"/api/v1/platform-ops/users/{self.member.pk}"
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())
        self.assertTrue(Organization.objects.filter(pk=self.org.pk).exists())
