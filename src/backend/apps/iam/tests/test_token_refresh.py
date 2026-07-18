from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.iam.services.token_service import (
    blacklist_all_user_tokens,
    generate_token_family_id,
    store_refresh_token_family,
)


class TokenRefreshTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="refresh-token@test.local",
            email="refresh-token@test.local",
            password="test-pass",
        )

    def _refresh_token(self) -> str:
        family_id = generate_token_family_id()
        refresh = RefreshToken.for_user(self.user)
        refresh["family_id"] = family_id
        token_version = store_refresh_token_family(
            self.user.id,
            family_id,
            refresh.payload.get("jti"),
        )
        refresh["token_version"] = token_version
        return str(refresh)

    def _token_pair(self) -> tuple[str, str]:
        family_id = generate_token_family_id()
        refresh = RefreshToken.for_user(self.user)
        refresh["family_id"] = family_id
        token_version = store_refresh_token_family(
            self.user.id,
            family_id,
            refresh.payload.get("jti"),
        )
        refresh["token_version"] = token_version
        access = AccessToken.for_user(self.user)
        access["token_version"] = token_version
        return str(access), str(refresh)

    def test_refresh_rotates_refresh_cookie_and_allows_consecutive_refreshes(self):
        original_refresh = self._refresh_token()
        self.client.cookies["refresh_token"] = original_refresh

        first = self.client.post("/api/v1/auth/token/refresh")

        self.assertEqual(first.status_code, status.HTTP_200_OK, first.content)
        self.assertIn("access_token", first.cookies)
        self.assertIn("refresh_token", first.cookies)
        rotated_refresh = first.cookies["refresh_token"].value
        self.assertNotEqual(rotated_refresh, original_refresh)

        self.client.cookies["refresh_token"] = rotated_refresh
        second = self.client.post("/api/v1/auth/token/refresh")

        self.assertEqual(second.status_code, status.HTTP_200_OK, second.content)
        self.assertIn("access_token", second.cookies)
        self.assertIn("refresh_token", second.cookies)

    def test_refresh_works_when_access_cookie_is_expired(self):
        refresh = self._refresh_token()
        expired_access = AccessToken.for_user(self.user)
        expired_access.set_exp(lifetime=-timedelta(seconds=1))
        self.client.cookies["access_token"] = str(expired_access)
        self.client.cookies["refresh_token"] = refresh

        response = self.client.post("/api/v1/auth/token/refresh")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)

    def test_expired_access_cookie_reports_token_expired(self):
        expired_access = AccessToken.for_user(self.user)
        expired_access.set_exp(lifetime=-timedelta(seconds=1))
        self.client.cookies["access_token"] = str(expired_access)

        response = self.client.get("/api/v1/auth/user")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(b"TOKEN_EXPIRED", response.content)
        self.assertNotIn(b"REFRESH_EXPIRED", response.content)

    def test_missing_access_cookie_reports_plain_unauthorized(self):
        response = self.client.get("/api/v1/auth/user")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(b"AUTH_401_UNAUTHORIZED", response.content)
        self.assertNotIn(b"REFRESH_EXPIRED", response.content)

    def test_session_probe_reports_signed_out_without_unauthorized_status(self):
        response = self.client.get("/api/v1/auth/token/refresh")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertFalse(response.data["authenticated"])
        self.assertFalse(response.data["refresh_available"])
        self.assertIsNone(response.data["user"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_session_probe_returns_user_for_valid_access_cookie(self):
        access, refresh = self._token_pair()
        self.client.cookies["access_token"] = access
        self.client.cookies["refresh_token"] = refresh

        response = self.client.get("/api/v1/auth/token/refresh")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertTrue(response.data["authenticated"])
        self.assertTrue(response.data["refresh_available"])
        self.assertEqual(response.data["user"]["id"], self.user.id)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_session_probe_marks_expired_access_as_refreshable(self):
        refresh = self._refresh_token()
        expired_access = AccessToken.for_user(self.user)
        expired_access.set_exp(lifetime=-timedelta(seconds=1))
        self.client.cookies["access_token"] = str(expired_access)
        self.client.cookies["refresh_token"] = refresh

        response = self.client.get("/api/v1/auth/token/refresh")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertFalse(response.data["authenticated"])
        self.assertTrue(response.data["refresh_available"])

    def test_reusing_rotated_refresh_token_is_rejected(self):
        original_refresh = self._refresh_token()
        self.client.cookies["refresh_token"] = original_refresh
        first = self.client.post("/api/v1/auth/token/refresh")
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.content)

        reuse_client = APIClient()
        reuse_client.cookies["refresh_token"] = original_refresh
        reuse = reuse_client.post("/api/v1/auth/token/refresh")

        self.assertEqual(reuse.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(b"TOKEN_REUSED", reuse.content)

    def test_new_login_invalidates_old_access_and_refresh_tokens(self):
        old_access, old_refresh = self._token_pair()

        blacklist_all_user_tokens(self.user.id, "new_login")
        self._token_pair()

        old_access_client = APIClient()
        old_access_client.cookies["access_token"] = old_access
        old_access_response = old_access_client.get("/api/v1/iam/orgs/")

        self.assertEqual(old_access_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(b"OTHER_DEVICE_LOGIN", old_access_response.content)

        old_refresh_client = APIClient()
        old_refresh_client.cookies["refresh_token"] = old_refresh
        old_refresh_response = old_refresh_client.post("/api/v1/auth/token/refresh")

        self.assertEqual(old_refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn(b"OTHER_DEVICE_LOGIN", old_refresh_response.content)
