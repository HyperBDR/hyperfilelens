"""PostgreSQL backend wrapper used for reliable test DB teardown."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from project.db.backends.postgresql.base import DatabaseCreation


class PostgresqlBackendCreationTests(SimpleTestCase):
    def test_destroy_terminates_other_sessions_before_drop(self) -> None:
        creation = DatabaseCreation(connection=MagicMock())
        cursor = MagicMock()
        nodb = MagicMock()
        nodb.__enter__.return_value = cursor
        nodb.__exit__.return_value = False
        creation._nodb_cursor = MagicMock(return_value=nodb)

        with patch.object(
            DatabaseCreation.__mro__[1],
            "_destroy_test_db",
            return_value=None,
        ) as parent_destroy:
            creation._destroy_test_db("test_hyperfilelens", verbosity=0)

        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args[0]
        self.assertIn("pg_terminate_backend", sql)
        self.assertEqual(params, ["test_hyperfilelens"])
        parent_destroy.assert_called_once_with("test_hyperfilelens", 0)
