from __future__ import annotations

import time
import uuid

from django.core.management.base import BaseCommand, CommandError

from apps.lens_bridge.models import LensSessionLink
from apps.lens_bridge.services.maintenance import (
    arm_sourcelens_maintenance,
    end_sourcelens_maintenance,
)
from apps.lens_bridge.services import copilot, sl_client, usage


class Command(BaseCommand):
    help = "Begin/end SourceLens maintenance and wait for active AI Runs to drain."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=("begin", "end", "check"))
        parser.add_argument("--timeout", type=int, default=600)

    @staticmethod
    def _active_admin_runs() -> dict[str, dict]:
        """Return every non-terminal SourceLens Run through admin pagination."""

        active: dict[str, dict] = {}
        page_size = 100
        for status in sorted(copilot.ACTIVE_RUN_STATUSES):
            for page in range(1, 1001):
                payload = sl_client.request_json(
                    "GET",
                    "/api/lens/admin/runs/",
                    params={
                        "page": page,
                        "page_size": page_size,
                        "status": status,
                    },
                )
                if not isinstance(payload, dict):
                    raise sl_client.LensBridgeError(
                        "SourceLens admin Run list returned an invalid payload."
                    )
                if "results" not in payload:
                    raise sl_client.LensBridgeError(
                        "SourceLens admin Run list omitted results."
                    )
                rows = payload["results"]
                if not isinstance(rows, list):
                    raise sl_client.LensBridgeError(
                        "SourceLens admin Run list returned invalid results."
                    )
                for run in rows:
                    if not isinstance(run, dict):
                        raise sl_client.LensBridgeError(
                            "SourceLens admin Run list returned a malformed row."
                        )
                    run_uuid_raw = run.get("uuid")
                    run_status = run.get("status")
                    if not isinstance(run_uuid_raw, str):
                        raise sl_client.LensBridgeError(
                            "SourceLens admin Run list returned an invalid UUID."
                        )
                    try:
                        run_uuid = str(uuid.UUID(run_uuid_raw))
                    except (ValueError, AttributeError):
                        raise sl_client.LensBridgeError(
                            "SourceLens admin Run list returned an invalid UUID."
                        ) from None
                    valid_statuses = (
                        copilot.ACTIVE_RUN_STATUSES | copilot.TERMINAL_RUN_STATUSES
                    )
                    if not isinstance(run_status, str) or run_status not in valid_statuses:
                        raise sl_client.LensBridgeError(
                            "SourceLens admin Run list returned an invalid status."
                        )
                    if run_status != status:
                        raise sl_client.LensBridgeError(
                            "SourceLens admin Run list returned an inconsistent status."
                        )
                    if run_status not in copilot.TERMINAL_RUN_STATUSES:
                        active[run_uuid] = run
                total = payload.get("total")
                if isinstance(total, bool) or not isinstance(total, int) or total < 0:
                    raise sl_client.LensBridgeError(
                        "SourceLens admin Run list returned an invalid total."
                    )
                if total < len(rows):
                    raise sl_client.LensBridgeError(
                        "SourceLens admin Run list returned an inconsistent total."
                    )
                offset = (page - 1) * page_size
                remaining = max(0, total - offset)
                expected_rows = min(page_size, remaining)
                if len(rows) != expected_rows:
                    raise sl_client.LensBridgeError(
                        "SourceLens admin Run pagination was inconsistent."
                    )
                if not rows or page * page_size >= total:
                    break
            else:
                raise sl_client.LensBridgeError(
                    "SourceLens admin Run pagination limit was reached."
                )
        return active

    @staticmethod
    def _active_run_count() -> int:
        try:
            active = Command._active_admin_runs()
        except sl_client.LensBridgeError:
            return 1
        links = LensSessionLink.objects.filter(active_run_uuid__isnull=False)
        for link in links:
            run_uuid = str(link.active_run_uuid)
            try:
                run = sl_client.request_json(
                    "GET",
                    f"/api/lens/admin/runs/{run_uuid}/",
                )
            except sl_client.LensBridgeError:
                # SourceLens is still expected to be online during the drain.
                # Unknown state is active: fail closed instead of interrupting
                # a Run whose status could not be fetched.
                active.setdefault(run_uuid, {})
                continue
            if not isinstance(run, dict):
                active.setdefault(run_uuid, {})
                continue
            status = str(run.get("status") or "")
            if status in copilot.TERMINAL_RUN_STATUSES:
                usage.capture_run_usage(link, run)
                copilot.clear_active_run(link)
                active.pop(run_uuid, None)
                continue
            if status and status != link.active_run_status:
                link.active_run_status = status
                link.save(update_fields=["active_run_status", "updated_at"])
            active[run_uuid] = run
        return len(active)

    def handle(self, *args, **options):
        action = options["action"]
        if action == "end":
            end_sourcelens_maintenance()
            self.stdout.write("SourceLens maintenance gate cleared")
            return
        if action == "check":
            active = self._active_run_count()
            if active:
                raise CommandError(f"{active} active SourceLens AI Run(s) remain")
            self.stdout.write("No active SourceLens AI Runs")
            return

        arm_sourcelens_maintenance()
        deadline = time.monotonic() + max(1, int(options["timeout"]))
        while time.monotonic() < deadline:
            active = self._active_run_count()
            if active == 0:
                self.stdout.write("SourceLens maintenance gate active; AI Runs drained")
                return
            self.stdout.write(f"Waiting for {active} SourceLens AI Run(s) to finish")
            time.sleep(2)
        raise CommandError("SourceLens AI Runs did not drain before timeout")
