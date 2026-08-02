#!/usr/bin/env python3
"""Run a guarded real-backup-to-Copilot test through one or more gateways."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from http.cookiejar import MozillaCookieJar
import json
import logging
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import time
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests
import urllib3


LOGGER = logging.getLogger("hfl-gateway-chat-e2e")
PRODUCTION_HOSTS = {
    "47.237.161.194",
    "app.hyperfilelens.com",
    "hyperfilelens.com",
}
EXPECTED_VALUES = {
    "project": "Aurora Glass",
    "retention": "37 days",
    "recovery": "BLUE-ORBIT-731",
}


class E2EError(RuntimeError):
    """Raised when an E2E precondition or assertion fails."""


class E2ERetryableError(E2EError):
    """Raised for transient HTTP failures that polling may safely retry."""


@dataclass(frozen=True)
class FixtureSet:
    """Filesystem fixture identity and expected answer values."""

    directory: Path
    values: dict[str, str]


class HflApi:
    """Small authenticated HFL JSON API client used by the E2E driver."""

    def __init__(
        self,
        *,
        base_url: str,
        org_key: str,
        verify_tls: bool,
        access_token: str = "",
        cookie_file: Path | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.verify_tls = verify_tls
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Org-Key": org_key,
            }
        )
        if access_token:
            self.session.headers["Authorization"] = f"Bearer {access_token}"
        if cookie_file is not None:
            jar = MozillaCookieJar(str(cookie_file))
            jar.load(ignore_discard=True, ignore_expires=True)
            self.session.cookies.update(jar)

    @staticmethod
    def unwrap(payload: Any) -> Any:
        """Remove HFL's standard response envelope when present."""
        if isinstance(payload, dict) and "code" in payload and "data" in payload:
            return payload.get("data")
        return payload

    def probe(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> tuple[int, Any]:
        """Return an HTTP status and decoded response without status assertions."""
        response = self.session.request(
            method,
            urljoin(self.base_url, path.lstrip("/")),
            json=json_body,
            params=params,
            timeout=timeout,
            verify=self.verify_tls,
        )
        if not response.content:
            return response.status_code, None
        try:
            payload = response.json()
        except ValueError:
            payload = response.text[:2000]
        return response.status_code, self.unwrap(payload)

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
        timeout: int = 30,
    ) -> Any:
        """Issue one API request and require an expected HTTP status."""
        status, payload = self.probe(
            method,
            path,
            json_body=json_body,
            params=params,
            timeout=timeout,
        )
        if status not in expected:
            error_type = E2ERetryableError if status >= 500 else E2EError
            raise error_type(
                f"{method.upper()} {path} returned HTTP {status}: "
                f"{json.dumps(payload, ensure_ascii=False)[:2000]}"
            )
        return payload


def validate_target(*, base_url: str, environment: str, allow_production: bool) -> None:
    """Reject accidental production execution unless explicitly unlocked."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise E2EError("--base-url must be an absolute HTTP(S) URL")
    production_target = parsed.hostname.lower() in PRODUCTION_HOSTS
    if production_target and environment != "production":
        raise E2EError("production hostname requires --environment production")
    if (environment == "production" or production_target) and not allow_production:
        raise E2EError("production execution requires --allow-production")


def create_fixtures(root: Path) -> FixtureSet:
    """Create an isolated three-file tree below a caller-approved backup root."""
    root = root.expanduser().resolve(strict=True)
    if not root.is_dir() or root == Path(root.anchor):
        raise E2EError("--fixture-root must be an existing non-root directory")
    run_id = (
        f"hfl-e2e-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    )
    directory = (root / run_id).resolve()
    if root not in directory.parents:
        raise E2EError("fixture directory escaped the approved root")
    (directory / "nested").mkdir(parents=True)
    (directory / "project.txt").write_text(
        EXPECTED_VALUES["project"] + "\n",
        encoding="utf-8",
    )
    (directory / "retention.txt").write_text(
        EXPECTED_VALUES["retention"] + "\n",
        encoding="utf-8",
    )
    (directory / "nested" / "recovery.txt").write_text(
        EXPECTED_VALUES["recovery"] + "\n",
        encoding="utf-8",
    )
    return FixtureSet(directory=directory, values=dict(EXPECTED_VALUES))


def wait_for(
    *,
    label: str,
    timeout_seconds: int,
    interval_seconds: float,
    check: Callable[[], Any | None],
) -> Any:
    """Poll until ``check`` returns a non-None result or timeout expires."""
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result is not None:
                return result
        except (requests.RequestException, E2ERetryableError) as exc:
            last_error = exc
        time.sleep(interval_seconds)
    detail = f": {last_error}" if last_error else ""
    raise E2EError(f"timed out waiting for {label}{detail}")


def trigger_backup(
    api: HflApi,
    *,
    backup_config_id: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Trigger a real backup and wait for its snapshot to become available."""
    idempotency_key = f"gateway-chat-e2e-{secrets.token_hex(8)}"
    result = api.request(
        "POST",
        "/api/v1/protection/backup-tasks/",
        json_body={
            "backup_config_ids": [backup_config_id],
            "trigger_type": "manual",
            "idempotency_key": idempotency_key,
        },
        expected=(201,),
    )
    rows = result.get("results", []) if isinstance(result, dict) else []
    row = next(
        (
            item
            for item in rows
            if int(item.get("backup_config_id") or 0) == backup_config_id
        ),
        None,
    )
    if not row or not row.get("source_snapshot_id"):
        raise E2EError(f"backup did not create a snapshot: {rows}")
    snapshot_id = int(row["source_snapshot_id"])

    def snapshot_ready() -> dict[str, Any] | None:
        snapshot = api.request(
            "GET",
            f"/api/v1/protection/backup-source-snapshots/{snapshot_id}/",
        )
        status = str(snapshot.get("status") or "")
        if status in {"failed", "partial", "delete_failed", "deleted"}:
            raise E2EError(
                f"snapshot {snapshot_id} entered terminal status {status}: "
                f"{snapshot.get('error_message', '')}"
            )
        return snapshot if status == "available" else None

    return wait_for(
        label=f"snapshot {snapshot_id}",
        timeout_seconds=timeout_seconds,
        interval_seconds=3,
        check=snapshot_ready,
    )


def select_snapshot_directory(
    snapshot: dict[str, Any],
    *,
    source_path: str,
    requested_id: int | None,
) -> dict[str, Any]:
    """Select the available configured root containing the fixture path."""
    directories = [
        row
        for row in snapshot.get("directories", [])
        if row.get("status") == "available"
    ]
    if requested_id is not None:
        selected = next(
            (row for row in directories if int(row.get("id") or 0) == requested_id),
            None,
        )
        if selected is None:
            raise E2EError(f"snapshot directory {requested_id} is not available")
        return selected

    fixture = PurePosixPath(source_path)
    candidates: list[dict[str, Any]] = []
    for row in directories:
        root = PurePosixPath(str(row.get("source_path") or ""))
        try:
            fixture.relative_to(root)
        except ValueError:
            continue
        candidates.append(row)
    if not candidates:
        raise E2EError(
            f"no available snapshot directory contains fixture path {source_path}"
        )
    return max(candidates, key=lambda row: len(str(row.get("source_path") or "")))


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_content_text(item) for item in value)
    if isinstance(value, dict):
        return "\n".join(_content_text(item) for item in value.values())
    return ""


def _assistant_answer(payload: dict[str, Any]) -> str:
    messages = payload.get("messages", [])
    return "\n".join(
        _content_text(row.get("content"))
        for row in messages
        if row.get("role") == "assistant"
    )


def create_and_verify_chat(
    api: HflApi,
    *,
    backup_config_id: int,
    snapshot: dict[str, Any],
    snapshot_directory: dict[str, Any],
    source_path: str,
    gateway_link_id: int,
    expected_values: dict[str, str],
    timeout_seconds: int,
    cleanup_registry: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create one gateway-bound Chat, ask about fixtures, and verify its answer."""
    session = api.request(
        "POST",
        "/api/v1/lens/copilot/sessions/",
        json_body={
            "title": f"Gateway E2E {gateway_link_id}",
            "backup_config_id": backup_config_id,
            "backup_source_snapshot_id": int(snapshot["id"]),
            "source_scopes": [
                {
                    "source_path": source_path,
                    "backup_snapshot_directory_id": int(snapshot_directory["id"]),
                    "path_type": "dir",
                }
            ],
            "gateway_mode": "manual",
            "gateway_link_id": gateway_link_id,
        },
        expected=(201,),
    )
    session_id = int(session["id"])
    tracked_result: dict[str, Any] = {
        "session_id": session_id,
        "knowledge_source_id": session.get("knowledge_source"),
    }
    cleanup_registry.append(tracked_result)

    def session_ready() -> dict[str, Any] | None:
        current = api.request(
            "GET",
            f"/api/v1/lens/copilot/sessions/{session_id}/",
        )
        lifecycle = str(current.get("lifecycle_status") or "")
        if lifecycle == "failed":
            raise E2EError(
                f"session {session_id} provisioning failed: "
                f"{current.get('lifecycle_error') or current.get('provision_detail')}"
            )
        return (
            current if lifecycle == "ready" and current.get("sl_session_uuid") else None
        )

    ready = wait_for(
        label=f"gateway {gateway_link_id} session provisioning",
        timeout_seconds=timeout_seconds,
        interval_seconds=3,
        check=session_ready,
    )
    question = (
        "Read project.txt, retention.txt, and nested/recovery.txt from the selected "
        "source. Reply with the exact values for project, retention, and recovery."
    )
    run = api.request(
        "POST",
        f"/api/v1/lens/copilot/sessions/{session_id}/runs/",
        json_body={
            "question": question,
            "idempotency_key": f"gateway-chat-e2e-{secrets.token_hex(8)}",
        },
        expected=(201,),
    )
    run_uuid = str(run.get("uuid") or "")
    if not run_uuid:
        raise E2EError(f"session {session_id} run returned no uuid")

    def answer_ready() -> str | None:
        sync = api.request(
            "GET",
            f"/api/v1/lens/copilot/sessions/{session_id}/sync/",
            timeout=60,
        )
        for outcome in sync.get("run_outcomes", []):
            if (
                str(outcome.get("run_uuid") or "") == run_uuid
                and outcome.get("status") == "failed"
            ):
                raise E2EError(
                    f"run {run_uuid} failed: {outcome.get('message', 'unknown error')}"
                )
        answer = _assistant_answer(sync)
        if answer and all(value in answer for value in expected_values.values()):
            return answer
        return None

    answer = wait_for(
        label=f"gateway {gateway_link_id} verified answer",
        timeout_seconds=timeout_seconds,
        interval_seconds=3,
        check=answer_ready,
    )
    tracked_result.update(
        {
            "knowledge_source_id": ready.get("knowledge_source"),
            "assistant_uuid": ready.get("sl_assistant_uuid"),
            "run_uuid": run_uuid,
            "answer": answer,
        }
    )
    return tracked_result


def cleanup_chat(api: HflApi, *, result: dict[str, Any], timeout_seconds: int) -> None:
    """Request durable Chat teardown and verify the HFL knowledge source disappears."""
    session_id = int(result["session_id"])
    status, _payload = api.probe(
        "DELETE",
        f"/api/v1/lens/copilot/sessions/{session_id}/",
    )
    if status not in {202, 204, 404}:
        raise E2EError(f"chat teardown returned HTTP {status} for session {session_id}")
    knowledge_source_id = result.get("knowledge_source_id")
    if not knowledge_source_id:
        return

    def knowledge_source_deleted() -> bool | None:
        current_status, payload = api.probe(
            "GET",
            f"/api/v1/lens/knowledge-sources/{knowledge_source_id}/",
        )
        if current_status == 404:
            return True
        if current_status != 200:
            raise E2EError(
                f"knowledge source cleanup probe returned HTTP {current_status}: {payload}"
            )
        return None

    wait_for(
        label=f"knowledge source {knowledge_source_id} teardown",
        timeout_seconds=timeout_seconds,
        interval_seconds=3,
        check=knowledge_source_deleted,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--environment", required=True, choices=("test", "preprod", "production")
    )
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--org-key", required=True)
    parser.add_argument("--cookie-file", type=Path)
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--backup-config-id", required=True, type=int)
    parser.add_argument("--gateway-link-id", required=True, type=int, action="append")
    parser.add_argument("--fixture-root", required=True, type=Path)
    parser.add_argument("--snapshot-directory-id", type=int)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--keep-session", action="store_true")
    parser.add_argument("--keep-fixtures", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute a real backup and Chat verification for every selected Gateway."""
    logging.basicConfig(level=logging.INFO, format="[gateway-chat-e2e] %(message)s")
    args = _parser().parse_args(argv)
    validate_target(
        base_url=args.base_url,
        environment=args.environment,
        allow_production=args.allow_production,
    )
    access_token = str(os.environ.get("HFL_E2E_ACCESS_TOKEN", ""))
    if not access_token and args.cookie_file is None:
        raise E2EError(
            "set HFL_E2E_ACCESS_TOKEN or provide --cookie-file; credentials are not accepted on the CLI"
        )
    if args.insecure:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    api = HflApi(
        base_url=args.base_url,
        org_key=args.org_key,
        verify_tls=not args.insecure,
        access_token=access_token,
        cookie_file=args.cookie_file,
    )
    api.request("GET", "/api/v1/auth/user")

    fixtures = create_fixtures(args.fixture_root)
    LOGGER.info("created fixtures under %s", fixtures.directory)
    chat_results: list[dict[str, Any]] = []
    try:
        snapshot = trigger_backup(
            api,
            backup_config_id=args.backup_config_id,
            timeout_seconds=args.timeout,
        )
        snapshot_directory = select_snapshot_directory(
            snapshot,
            source_path=str(fixtures.directory),
            requested_id=args.snapshot_directory_id,
        )
        LOGGER.info(
            "snapshot %s available; directory root=%s",
            snapshot["id"],
            snapshot_directory.get("source_path"),
        )
        for gateway_link_id in args.gateway_link_id:
            result = create_and_verify_chat(
                api,
                backup_config_id=args.backup_config_id,
                snapshot=snapshot,
                snapshot_directory=snapshot_directory,
                source_path=str(fixtures.directory),
                gateway_link_id=gateway_link_id,
                expected_values=fixtures.values,
                timeout_seconds=args.timeout,
                cleanup_registry=chat_results,
            )
            LOGGER.info(
                "gateway %s answered all fixture values (session=%s)",
                gateway_link_id,
                result["session_id"],
            )
            if not args.keep_session:
                cleanup_chat(api, result=result, timeout_seconds=args.timeout)
                LOGGER.info("gateway %s Chat resources cleaned", gateway_link_id)

        retained = api.request(
            "GET",
            f"/api/v1/protection/backup-source-snapshots/{snapshot['id']}/",
        )
        if retained.get("status") != "available":
            raise E2EError("Chat cleanup unexpectedly changed the backup snapshot")
        print(
            json.dumps(
                {
                    "status": "passed",
                    "snapshot_id": snapshot["id"],
                    "gateway_link_ids": args.gateway_link_id,
                    "sessions": [result["session_id"] for result in chat_results],
                    "backup_retained": True,
                },
                ensure_ascii=False,
            )
        )
    finally:
        if not args.keep_session:
            for result in reversed(chat_results):
                try:
                    cleanup_chat(api, result=result, timeout_seconds=args.timeout)
                except (requests.RequestException, E2EError):
                    LOGGER.exception(
                        "best-effort Chat cleanup failed session=%s",
                        result.get("session_id"),
                    )
        if not args.keep_fixtures:
            shutil.rmtree(fixtures.directory, ignore_errors=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (E2EError, requests.RequestException) as exc:
        LOGGER.error("%s", exc)
        raise SystemExit(1) from exc
