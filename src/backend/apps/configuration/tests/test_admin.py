"""Tests for configuration Django Admin registration."""

import importlib

from django.contrib import admin
from django.test import TestCase

from apps.configuration.models import GlobalConfig


class GlobalConfigAdminRegistrationTest(TestCase):
    def test_admin_module_upgrades_default_registration(self):
        if admin.site.is_registered(GlobalConfig):
            admin.site.unregister(GlobalConfig)

        admin.site.register(GlobalConfig)
        self.assertEqual(admin.site._registry[GlobalConfig].__class__, admin.ModelAdmin)

        import apps.configuration.admin as config_admin

        importlib.reload(config_admin)

        self.assertTrue(admin.site.is_registered(GlobalConfig))
        self.assertEqual(
            admin.site._registry[GlobalConfig].__class__.__name__,
            "GlobalConfigAdmin",
        )

    def test_admin_module_reload_is_idempotent(self):
        import apps.configuration.admin as config_admin

        importlib.reload(config_admin)
        importlib.reload(config_admin)

        self.assertTrue(admin.site.is_registered(GlobalConfig))
        self.assertEqual(
            admin.site._registry[GlobalConfig].__class__.__name__,
            "GlobalConfigAdmin",
        )
