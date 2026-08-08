"""PostgreSQL backend with reliable test-database teardown.

Threaded / async leftovers can keep sessions on ``test_*`` after the suite
reports OK; plain ``DROP DATABASE`` then fails with ObjectInUse. Terminate
those backends before destroy (production connections are unchanged).
"""

from __future__ import annotations

from django.db.backends.postgresql.base import DatabaseWrapper as PostgresDatabaseWrapper
from django.db.backends.postgresql.creation import DatabaseCreation as PostgresDatabaseCreation


class DatabaseCreation(PostgresDatabaseCreation):
    def _destroy_test_db(self, test_database_name, verbosity):
        with self._nodb_cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s
                  AND pid <> pg_backend_pid()
                """,
                [test_database_name],
            )
        return super()._destroy_test_db(test_database_name, verbosity)


class DatabaseWrapper(PostgresDatabaseWrapper):
    creation_class = DatabaseCreation
