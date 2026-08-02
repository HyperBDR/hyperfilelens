"""Unit tests for the guarded Gateway/Chat E2E driver."""

from pathlib import Path
import tempfile
import unittest

from gateway_chat import (
    E2EError,
    E2ERetryableError,
    EXPECTED_VALUES,
    HflApi,
    create_fixtures,
    select_snapshot_directory,
    validate_target,
    wait_for,
)


class GatewayChatToolTests(unittest.TestCase):
    def test_response_envelope_is_unwrapped(self) -> None:
        self.assertEqual(
            HflApi.unwrap({"code": "0000", "message": "ok", "data": {"id": 1}}),
            {"id": 1},
        )

    def test_production_target_requires_explicit_unlock(self) -> None:
        with self.assertRaises(E2EError):
            validate_target(
                base_url="https://app.hyperfilelens.com",
                environment="production",
                allow_production=False,
            )

    def test_fixture_tree_is_isolated_below_approved_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixtures = create_fixtures(Path(temporary))

            self.assertIn(Path(temporary).resolve(), fixtures.directory.parents)
            self.assertEqual(
                (fixtures.directory / "project.txt")
                .read_text(encoding="utf-8")
                .strip(),
                EXPECTED_VALUES["project"],
            )
            self.assertEqual(
                (fixtures.directory / "nested" / "recovery.txt")
                .read_text(encoding="utf-8")
                .strip(),
                EXPECTED_VALUES["recovery"],
            )

    def test_most_specific_available_snapshot_root_is_selected(self) -> None:
        snapshot = {
            "directories": [
                {"id": 1, "status": "available", "source_path": "/srv/data"},
                {"id": 2, "status": "available", "source_path": "/srv/data/team"},
            ]
        }

        selected = select_snapshot_directory(
            snapshot,
            source_path="/srv/data/team/hfl-e2e-1",
            requested_id=None,
        )

        self.assertEqual(selected["id"], 2)

    def test_terminal_assertion_is_not_hidden_until_poll_timeout(self) -> None:
        calls = 0

        def terminal_failure():
            nonlocal calls
            calls += 1
            raise E2EError("snapshot failed")

        with self.assertRaisesRegex(E2EError, "snapshot failed"):
            wait_for(
                label="terminal failure",
                timeout_seconds=30,
                interval_seconds=0,
                check=terminal_failure,
            )
        self.assertEqual(calls, 1)

    def test_transient_failure_is_retried(self) -> None:
        calls = 0

        def eventually_ready():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise E2ERetryableError("temporary 503")
            return "ready"

        result = wait_for(
            label="transient failure",
            timeout_seconds=1,
            interval_seconds=0,
            check=eventually_ready,
        )

        self.assertEqual(result, "ready")
        self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
