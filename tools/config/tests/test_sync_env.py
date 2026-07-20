from __future__ import annotations

import io
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tools.config.sync_env import main, sync_env_file


class SyncEnvFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.env_path = self.root / ".env"
        self.example_path = self.root / ".env.example"

    def test_adds_missing_defaults_and_preserves_existing_content(self) -> None:
        self.env_path.write_text(
            "# Local settings\n"
            "EXISTING_VALUE=custom\n"
            "HFL_REGISTRATION_ENABLED=true\n",
            encoding="utf-8",
        )
        os.chmod(self.env_path, 0o600)
        self.example_path.write_text(
            "EXISTING_VALUE=default\n"
            "HFL_EMAIL_SIGNUP_ENABLED=false\n"
            "HFL_GOOGLE_OAUTH_ENABLED=false\n",
            encoding="utf-8",
        )

        result = sync_env_file(self.env_path, self.example_path)

        self.assertEqual(
            result.added_keys,
            ("HFL_EMAIL_SIGNUP_ENABLED", "HFL_GOOGLE_OAUTH_ENABLED"),
        )
        self.assertEqual(result.deprecated_keys, ("HFL_REGISTRATION_ENABLED",))
        self.assertEqual(
            self.env_path.read_text(encoding="utf-8"),
            "# Local settings\n"
            "EXISTING_VALUE=custom\n"
            "HFL_REGISTRATION_ENABLED=true\n"
            "HFL_EMAIL_SIGNUP_ENABLED=false\n"
            "HFL_GOOGLE_OAUTH_ENABLED=false\n",
        )
        self.assertEqual(stat.S_IMODE(self.env_path.stat().st_mode), 0o600)

    def test_does_not_overwrite_existing_or_unknown_values(self) -> None:
        original = (
            "CUSTOM_EXTENSION=keep-me\n"
            "HFL_EMAIL_SIGNUP_ENABLED=true\n"
            "HFL_GOOGLE_OAUTH_ENABLED=true\n"
        )
        self.env_path.write_text(original, encoding="utf-8")
        self.example_path.write_text(
            "HFL_EMAIL_SIGNUP_ENABLED=false\n"
            "HFL_GOOGLE_OAUTH_ENABLED=false\n",
            encoding="utf-8",
        )

        result = sync_env_file(self.env_path, self.example_path)

        self.assertEqual(result.added_keys, ())
        self.assertEqual(result.deprecated_keys, ())
        self.assertEqual(self.env_path.read_text(encoding="utf-8"), original)

    def test_repeated_sync_is_idempotent(self) -> None:
        self.env_path.write_text("HFL_REGISTRATION_ENABLED=true", encoding="utf-8")
        self.example_path.write_text(
            "HFL_EMAIL_SIGNUP_ENABLED=false\n",
            encoding="utf-8",
        )

        first = sync_env_file(self.env_path, self.example_path)
        content_after_first = self.env_path.read_bytes()
        second = sync_env_file(self.env_path, self.example_path)

        self.assertEqual(first.added_keys, ("HFL_EMAIL_SIGNUP_ENABLED",))
        self.assertEqual(second.added_keys, ())
        self.assertEqual(second.deprecated_keys, ("HFL_REGISTRATION_ENABLED",))
        self.assertEqual(self.env_path.read_bytes(), content_after_first)

    def test_cli_reports_added_and_deprecated_keys(self) -> None:
        self.env_path.write_text(
            "HFL_REGISTRATION_ENABLED=true\n",
            encoding="utf-8",
        )
        self.example_path.write_text(
            "HFL_EMAIL_SIGNUP_ENABLED=false\n",
            encoding="utf-8",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                [
                    "--env-file",
                    str(self.env_path),
                    "--example",
                    str(self.example_path),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("Added env keys: HFL_EMAIL_SIGNUP_ENABLED", stdout.getvalue())
        self.assertIn(
            "HFL_REGISTRATION_ENABLED is deprecated and ignored",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
