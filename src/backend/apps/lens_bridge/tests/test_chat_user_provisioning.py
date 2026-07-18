from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase, override_settings

from apps.lens_bridge.services import chat_user_provisioning


@override_settings(SECRET_KEY="test-hfl-secret")
class ChatUserProvisioningTests(SimpleTestCase):
    def setUp(self):
        chat_user_provisioning.invalidate_user_token(7)
        self.user = SimpleNamespace(pk=7, username="alice")

    @patch("apps.lens_bridge.services.chat_user_provisioning.sl_client.request_json")
    def test_provisions_chat_user_through_management_api(self, request_json):
        request_json.side_effect = [
            {"count": 0, "results": []},
            {"id": 23, "username": "hfl-u-7"},
        ]
        link = Mock(sl_username="hfl-u-7")

        chat_user_provisioning._provision_remote(
            self.user,
            link=link,
            gateway_operator=False,
        )

        self.assertEqual(
            request_json.call_args_list,
            [
                call(
                    "GET",
                    "/api/v1/management/users/",
                    params={"page": 1, "page_size": 100},
                ),
                call(
                    "POST",
                    "/api/v1/management/users/",
                    json_body={
                        "username": "hfl-u-7",
                        "email": "",
                        "password": chat_user_provisioning._sl_password_for_hfl_user(
                            self.user
                        ),
                        "is_staff": False,
                        "role_ids": [],
                        "preferred_platform": "workspace",
                    },
                ),
            ],
        )
        self.assertEqual(link.sl_user_id, 23)
        link.save.assert_called_once()

    @patch("apps.lens_bridge.services.chat_user_provisioning.sl_client.login_user")
    @patch("apps.lens_bridge.services.chat_user_provisioning.ensure_sl_chat_user")
    def test_mints_token_by_logging_in_as_chat_user(self, ensure_user, login_user):
        ensure_user.return_value = SimpleNamespace(
            sl_user_id=23,
            sl_username="hfl-u-7",
        )
        login_user.return_value = "chat-access-token"

        token = chat_user_provisioning.mint_sl_access_token(self.user)

        self.assertEqual(token, "chat-access-token")
        login_user.assert_called_once_with(
            username="hfl-u-7",
            password=chat_user_provisioning._sl_password_for_hfl_user(self.user),
        )
