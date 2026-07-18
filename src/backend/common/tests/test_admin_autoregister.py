"""Tests for Django Admin auto-registration."""

from django.contrib import admin
from django.test import TestCase

from apps.protection.models.backup_policy import BackupPolicy
from common.admin_autoregister import autoregister_project_models


class AdminAutoregisterTest(TestCase):
    def test_unregistered_project_models_get_registered(self):
        if admin.site.is_registered(BackupPolicy):
            admin.site.unregister(BackupPolicy)

        count = autoregister_project_models()
        self.assertGreaterEqual(count, 1)
        self.assertTrue(admin.site.is_registered(BackupPolicy))

    def test_already_registered_models_are_skipped(self):
        first = autoregister_project_models()
        second = autoregister_project_models()
        self.assertEqual(second, 0)
        self.assertGreaterEqual(first, 0)
