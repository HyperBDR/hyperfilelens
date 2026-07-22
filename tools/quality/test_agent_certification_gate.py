"""Tests for the tagged Agent native-certification release gate."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "release" / "ci" / "verify-agent-certifications.py"


class AgentCertificationGateTests(unittest.TestCase):
    def test_accepts_report_bound_to_candidate_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            candidates = root / "candidates"
            reports = root / "reports"
            candidates.mkdir()
            reports.mkdir()
            package_name, package_hash = self._write_candidate(candidates)
            self._write_report(reports, package_name, package_hash)
            output = root / "summary.json"

            result = self._run_gate(candidates, reports, output)
            self.assertEqual(result.returncode, 0, result.stdout)
            summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")

    def test_rejects_report_for_different_candidate_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            candidates = root / "candidates"
            reports = root / "reports"
            candidates.mkdir()
            reports.mkdir()
            package_name, _package_hash = self._write_candidate(candidates)
            self._write_report(reports, package_name, "0" * 64)

            result = self._run_gate(candidates, reports, root / "summary.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("digest mismatch", result.stdout)

    def test_rejects_skipped_native_certification_step(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            candidates = root / "candidates"
            reports = root / "reports"
            candidates.mkdir()
            reports.mkdir()
            package_name, package_hash = self._write_candidate(candidates)
            self._write_report(reports, package_name, package_hash)
            report_path = reports / "_internal-agent-cert-linux-amd64.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["tests"]["enrollment"] = "skipped"
            report_path.write_text(json.dumps(report), encoding="utf-8")

            result = self._run_gate(candidates, reports, root / "summary.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("enrollment", result.stdout)

    def _write_candidate(self, destination: pathlib.Path) -> tuple[str, str]:
        package_name = "hfl-agent-1.2.3-linux-amd64.tar.gz"
        package_data = b"immutable-agent-package"
        package_hash = hashlib.sha256(package_data).hexdigest()
        bundle = destination / "_internal-agent-linux-amd64.tar.gz"
        with tempfile.TemporaryDirectory() as staging_value:
            staging = pathlib.Path(staging_value)
            package = (
                staging
                / "payload"
                / "media"
                / "agent-releases"
                / "1.2.3"
                / package_name
            )
            package.parent.mkdir(parents=True)
            package.write_bytes(package_data)
            with tarfile.open(bundle, "w:gz") as archive:
                archive.add(staging / "payload", arcname="payload")
        return package_name, package_hash

    def _write_report(
        self, destination: pathlib.Path, package_name: str, package_hash: str
    ) -> None:
        tests = {
            name: "passed"
            for name in (
                "candidate_manifest",
                "native_binaries",
                "backup",
                "verify",
                "restore",
                "metadata",
                "enrollment",
                "service_start",
                "uninstall",
            )
        }
        report = {
            "schema": 1,
            "tag": "v1.2.3",
            "version": "1.2.3",
            "commit": "a" * 40,
            "artifact": {"name": package_name, "sha256": package_hash},
            "platform": {"os_family": "linux", "arch": "amd64"},
            "tests": tests,
        }
        path = destination / "_internal-agent-cert-linux-amd64.json"
        path.write_text(json.dumps(report), encoding="utf-8")

    def _run_gate(
        self, candidates: pathlib.Path, reports: pathlib.Path, output: pathlib.Path
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(GATE),
                "--candidates-dir",
                str(candidates),
                "--reports-dir",
                str(reports),
                "--version",
                "1.2.3",
                "--commit",
                "a" * 40,
                "--required-target",
                "linux:amd64",
                "--output",
                str(output),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
