from __future__ import annotations

import time

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
    def _active_run_count() -> int:
        active = 0
        links = LensSessionLink.objects.select_related("hfl_user").filter(
            active_run_uuid__isnull=False
        )
        for link in links:
            try:
                run = sl_client.request_json(
                    "GET",
                    f"/api/lens/runs/{link.active_run_uuid}/",
                    hfl_user=link.hfl_user,
                )
            except sl_client.LensBridgeError:
                # SourceLens is still expected to be online during the drain.
                # Unknown state is active: fail closed instead of interrupting
                # a Run whose status could not be fetched.
                active += 1
                continue
            status = str(run.get("status") or "")
            if status in copilot.TERMINAL_RUN_STATUSES:
                usage.capture_run_usage(link, run)
                copilot.clear_active_run(link)
                continue
            if status and status != link.active_run_status:
                link.active_run_status = status
                link.save(update_fields=["active_run_status", "updated_at"])
            active += 1
        return active

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
