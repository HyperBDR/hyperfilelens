from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.iam.services.token_service import (
    blacklist_all_user_tokens,
    generate_token_family_id,
    store_refresh_token_family,
)


class ChangePasswordApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="change-password@test.local",
            email="change-password@test.local",
            password="OldPass123",
            is_active=True,
        )
        self.url = reverse("change_password")

    def _auth_client(self, user=None):
        user = user or self.user
        family_id = generate_token_family_id()
        refresh = RefreshToken.for_user(user)
        refresh["family_id"] = family_id
        token_version = store_refresh_token_family(user.id, family_id, refresh.payload.get("jti"))
        refresh["token_version"] = token_version

        access = AccessToken.for_user(user)
        access["token_version"] = token_version

        client = APIClient()
        client.cookies["access_token"] = str(access)
        client.cookies["refresh_token"] = str(refresh)
        return client

    def test_requires_authentication(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalidated_token_cannot_change_password(self):
        client = self._auth_client()
        blacklist_all_user_tokens(self.user.id, "password_changed")

        response = client.post(
            self.url,
            {
                "current_password": "OldPass123",
                "new_password": "NewPass123",
                "confirm_password": "NewPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(b"PASSWORD_CHANGED", response.content)

    def test_current_password_error_maps_to_field(self):
        client = self._auth_client()

        response = client.post(
            self.url,
            {
                "current_password": "WrongPass123",
                "new_password": "NewPass123",
                "confirm_password": "NewPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "1001")
        self.assertIn("current_password", response.data["error"]["fields"])

    def test_new_password_error_maps_to_field(self):
        client = self._auth_client()

        response = client.post(
            self.url,
            {
                "current_password": "OldPass123",
                "new_password": "lowercase123",
                "confirm_password": "lowercase123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "1001")
        self.assertIn("new_password", response.data["error"]["fields"])

    def test_confirm_password_error_maps_to_field(self):
        client = self._auth_client()

        response = client.post(
            self.url,
            {
                "current_password": "OldPass123",
                "new_password": "NewPass123",
                "confirm_password": "Different123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "1001")
        self.assertIn("confirm_password", response.data["error"]["fields"])

    def test_success_changes_password_and_invalidates_old_tokens(self):
        client = self._auth_client()
        old_access = client.cookies["access_token"].value
        old_refresh = client.cookies["refresh_token"].value

        response = client.post(
            self.url,
            {
                "current_password": "OldPass123",
                "new_password": "NewPass123",
                "confirm_password": "NewPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data["code"], "0000")
        self.assertTrue(response.data["data"]["requires_relogin"])
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)

        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("OldPass123"))
        self.assertTrue(self.user.check_password("NewPass123"))

        old_token_client = APIClient()
        old_token_client.cookies["access_token"] = old_access
        invalid = old_token_client.get("/api/v1/auth/user")

        self.assertEqual(invalid.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(b"PASSWORD_CHANGED", invalid.content)

        old_refresh_client = APIClient()
        old_refresh_client.cookies["refresh_token"] = old_refresh
        refresh = old_refresh_client.post("/api/v1/auth/token/refresh")

        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(b"PASSWORD_CHANGED", refresh.content)
