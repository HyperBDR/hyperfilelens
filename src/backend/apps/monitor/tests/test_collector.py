"""Collector unit tests."""

from django.test import TestCase

from apps.monitor.services.internal.collector import collect_system_sample


class CollectorTests(TestCase):
    def test_collect_returns_required_keys(self):
        sample = collect_system_sample()
        for key in ("cpu", "memory", "swap", "disks", "disk_io", "networks", "load_average", "metadata"):
            self.assertIn(key, sample)
        self.assertIn("usage_percent", sample["cpu"])
