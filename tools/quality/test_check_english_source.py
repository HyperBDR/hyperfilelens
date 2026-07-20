#!/usr/bin/env python3
"""Regression tests for the English-only public source checker."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER_SOURCE = Path(__file__).with_name("check-english-source.py")


class EnglishSourceCheckerTests(unittest.TestCase):
    """Verify that the checker follows Git's public source boundary."""

    def setUp(self) -> None:
        """Create an isolated Git repository containing the checker."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository_root = Path(self.temporary_directory.name)
        checker = self.repository_root / "tools/quality/check-english-source.py"
        checker.parent.mkdir(parents=True)
        shutil.copy2(CHECKER_SOURCE, checker)
        (self.repository_root / ".gitignore").write_text(
            ".tmp/\n",
            encoding="utf-8",
        )
        self.run_git("init", "--quiet")
        self.run_git("add", ".gitignore", "tools/quality/check-english-source.py")

    def run_git(self, *arguments: str) -> None:
        """Run Git in the isolated repository."""
        subprocess.run(
            ["git", *arguments],
            cwd=self.repository_root,
            check=True,
            stdout=subprocess.PIPE,
        )

    def run_checker(self) -> subprocess.CompletedProcess[str]:
        """Run the copied checker and return its captured result."""
        return subprocess.run(
            [sys.executable, "tools/quality/check-english-source.py"],
            cwd=self.repository_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_ignored_file_is_not_checked(self) -> None:
        """Ignore local files even when their paths and contents contain CJK."""
        ignored_directory = self.repository_root / ".tmp"
        ignored_directory.mkdir()
        (ignored_directory / "\u4f60\u597d.txt").write_text(
            "\u4f60\u597d\n",
            encoding="utf-8",
        )

        result = self.run_checker()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("English-only source check passed.", result.stdout)

    def test_untracked_nonignored_file_is_checked(self) -> None:
        """Check new source files before they are added to Git."""
        (self.repository_root / "notes.txt").write_text(
            "\u4f60\n",
            encoding="utf-8",
        )

        result = self.run_checker()

        self.assertEqual(result.returncode, 1)
        self.assertIn("notes.txt:1:1", result.stdout)
        self.assertIn("U+4F60", result.stdout)

    def test_tracked_file_is_checked_even_when_ignored(self) -> None:
        """Keep checking tracked files after an ignore rule is introduced."""
        tracked_file = self.repository_root / "tracked.txt"
        tracked_file.write_text("\u4f60\n", encoding="utf-8")
        self.run_git("add", "tracked.txt")
        with (self.repository_root / ".gitignore").open(
            "a",
            encoding="utf-8",
        ) as ignore_file:
            ignore_file.write("tracked.txt\n")

        result = self.run_checker()

        self.assertEqual(result.returncode, 1)
        self.assertIn("tracked.txt:1:1", result.stdout)


if __name__ == "__main__":
    unittest.main()
