from django.test import RequestFactory, TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from apps.iam.profile_models import Profile
from apps.iam.services.login_audit import (
    LOGIN_LOCATION_LOCAL_NETWORK,
    get_security_audit,
    record_user_login,
    resolve_login_location,
    serialize_security_audit,
)
from apps.iam.auth.serializers import get_registered_at


class LoginAuditServiceTests(TestCase):
    legacy_local_network_label = "\u5c40\u57df\u7f51"

    def setUp(self):
        self.user = User.objects.create_user(
            username="audit-user",
            email="audit@example.com",
            password="Audit@12345",
        )
        Profile.objects.create(user=self.user)
        self.factory = RequestFactory()

    def test_resolve_login_location_private_ip(self):
        request = self.factory.get("/", REMOTE_ADDR="192.168.1.105")
        self.assertEqual(resolve_login_location("192.168.1.105", request), LOGIN_LOCATION_LOCAL_NETWORK)

    def test_get_security_audit_falls_back_to_audit_log(self):
        from apps.audit.constants import AuditAction, AuditResult
        from apps.audit.models import AuditLog
        from apps.iam.models import Organization

        org = Organization.objects.create(key="audit-org", name="Audit Org")
        logged_at = timezone.now() - timezone.timedelta(hours=2)
        AuditLog.objects.create(
            organization=org,
            user=self.user,
            action=AuditAction.LOGIN,
            result=AuditResult.SUCCESS,
            ip_address="192.168.1.105",
            metadata={"location": self.legacy_local_network_label},
            created_at=logged_at,
        )

        audit = get_security_audit(self.user)
        self.assertEqual(audit["last_login_ip"], "192.168.1.105")
        self.assertEqual(audit["last_login_location"], self.legacy_local_network_label)
        self.assertEqual(
            serialize_security_audit(audit)["last_login_location"],
            LOGIN_LOCATION_LOCAL_NETWORK,
        )
        self.assertIsNotNone(audit["last_login_at"])

    def test_get_registered_at_prefers_profile_timestamp(self):
        registered = timezone.now() - timezone.timedelta(days=30)
        profile = self.user.profile
        profile.registered_at = registered
        profile.save(update_fields=["registered_at"])

        value = get_registered_at(self.user)
        self.assertEqual(value, registered)

    def test_serialize_security_audit_normalizes_legacy_local_network_label(self):
        audit = serialize_security_audit(
            {"last_login_location": self.legacy_local_network_label},
        )
        self.assertEqual(audit["last_login_location"], LOGIN_LOCATION_LOCAL_NETWORK)

    def test_record_user_login_shifts_previous_login(self):
        first_login = timezone.now()
        self.user.last_login = first_login
        self.user.save(update_fields=["last_login"])

        profile = self.user.profile
        profile.last_login_ip = "10.0.0.8"
        profile.last_login_location = self.legacy_local_network_label
        profile.save(update_fields=["last_login_ip", "last_login_location"])

        request = self.factory.get("/", REMOTE_ADDR="203.0.113.10")
        record_user_login(self.user, request, organization=None)

        self.user.refresh_from_db()
        profile.refresh_from_db()
        audit = get_security_audit(self.user)

        self.assertEqual(audit["last_login_ip"], "203.0.113.10")
        self.assertEqual(profile.previous_login_ip, "10.0.0.8")
        self.assertEqual(profile.previous_login_at, first_login)
        self.assertIsNotNone(self.user.last_login)
        self.assertGreater(self.user.last_login, first_login)
