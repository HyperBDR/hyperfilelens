"""Tests for the supported application database configuration."""

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from project.settings.database import _build_default_db_config


class DatabaseSettingsTests(SimpleTestCase):
    """Verify that public deployments use PostgreSQL exclusively."""

    def test_postgresql_url_is_accepted(self) -> None:
        config = _build_default_db_config(
            "postgresql://hyperfilelens:secret@postgres:5432/hyperfilelens"
        )

        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["CONN_MAX_AGE"], 0)
        self.assertEqual(config["OPTIONS"]["connect_timeout"], 60)

    def test_sqlite_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ImproperlyConfigured, "PostgreSQL only"):
            _build_default_db_config("sqlite:////tmp/hyperfilelens.sqlite3")

    def test_mysql_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ImproperlyConfigured, "PostgreSQL only"):
            _build_default_db_config(
                "mysql://hyperfilelens:secret@mysql:3306/hyperfilelens"
            )
