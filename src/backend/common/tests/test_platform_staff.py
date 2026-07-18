from django.contrib.auth.models import User
from django.test import TestCase

from common.platform_staff import apply_platform_staff


class PlatformStaffSyncTest(TestCase):
    def test_apply_platform_staff_grants_superuser(self):
        user = User.objects.create_user(
            username="staff@test.com",
            email="staff@test.com",
            password="Pass1234",
        )
        apply_platform_staff(user, True)
        user.save(update_fields=["is_staff", "is_superuser"])
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_apply_platform_staff_revokes_superuser(self):
        user = User.objects.create_user(
            username="revoke@test.com",
            email="revoke@test.com",
            password="Pass1234",
            is_staff=True,
            is_superuser=True,
        )
        apply_platform_staff(user, False)
        user.save(update_fields=["is_staff", "is_superuser"])
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
