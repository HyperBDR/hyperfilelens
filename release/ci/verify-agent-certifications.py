#!/usr/bin/env python3
"""Gate an immutable artifact on native Source Host certification reports."""

from __future__ import annotations

import argparse
import json
import hashlib
import pathlib
import tarfile


REQUIRED_TESTS = {
    "candidate_manifest",
    "native_binaries",
    "backup",
    "verify",
    "restore",
    "metadata",
    "enrollment",
    "service_start",
    "uninstall",
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def artifact_id(version: str) -> str:
    return version if version.startswith("main-") else f"v{version}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", required=True, type=pathlib.Path)
    parser.add_argument("--candidates-dir", required=True, type=pathlib.Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--required-target", action="append", default=[])
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    expected_artifact_id = artifact_id(args.version)

    candidate_hashes: dict[str, str] = {}
    for bundle in sorted(args.candidates_dir.glob("_internal-agent-*.tar.gz")):
        with tarfile.open(bundle, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile() or "/agent-releases/" not in member.name:
                    continue
                name = pathlib.PurePosixPath(member.name).name
                if not (name.endswith(".tar.gz") or name.endswith(".zip")):
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    fail(f"cannot read {member.name} from {bundle.name}")
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                actual = digest.hexdigest()
                if name in candidate_hashes and candidate_hashes[name] != actual:
                    fail(f"conflicting candidate package bytes for {name}")
                candidate_hashes[name] = actual

    reports: dict[str, dict] = {}
    for path in sorted(args.reports_dir.glob("_internal-agent-cert-*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        platform_info = value.get("platform") or {}
        target = f"{platform_info.get('os_family')}:{platform_info.get('arch')}"
        if target in reports:
            fail(f"duplicate certification report for {target}")
        if value.get("schema") != 1:
            fail(f"unsupported report schema in {path.name}")
        if (
            value.get("version") != args.version
            or value.get("tag") != expected_artifact_id
        ):
            fail(f"version mismatch in {path.name}")
        if value.get("commit") != args.commit:
            fail(f"commit mismatch in {path.name}")
        artifact = value.get("artifact") or {}
        if not artifact.get("name") or len(str(artifact.get("sha256") or "")) != 64:
            fail(f"invalid artifact evidence in {path.name}")
        expected_hash = candidate_hashes.get(str(artifact["name"]))
        if not expected_hash:
            fail(f"tested artifact is not present in candidate bundles: {artifact['name']}")
        if artifact["sha256"] != expected_hash:
            fail(f"tested artifact digest mismatch for {artifact['name']}")
        tests = value.get("tests") or {}
        missing = sorted(REQUIRED_TESTS - set(tests))
        failed = sorted(name for name in REQUIRED_TESTS if tests.get(name) != "passed")
        if missing or failed:
            fail(f"certification failed for {target}: missing={missing}, failed={failed}")
        reports[target] = value

    required = set(args.required_target)
    missing_targets = sorted(required - set(reports))
    if missing_targets:
        fail(f"required certification reports are missing: {', '.join(missing_targets)}")

    summary = {
        "schema": 1,
        "tag": expected_artifact_id,
        "version": args.version,
        "commit": args.commit,
        "required_targets": sorted(required),
        "reports": [reports[target] for target in sorted(reports)],
        "status": "passed",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Source Host release gate passed for {len(reports)} native targets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
