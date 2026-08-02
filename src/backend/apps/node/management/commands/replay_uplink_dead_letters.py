"""Replay quarantined Agent uplink messages from the Redis dead-letter stream."""

from django.core.management.base import BaseCommand, CommandError
from redis.exceptions import RedisError

from apps.node.services.internal import redis_store
from apps.node.ws.uplink_queue import (
    NODE_UPLINK_DEAD_LETTER_STREAM,
    replay_dead_letter_entry,
)


class Command(BaseCommand):
    help = "Replay Agent uplink dead letters into the live projection stream."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--entry-id",
            action="append",
            default=[],
            help="Exact DLQ Stream entry ID to replay; may be repeated.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Replay at most this many oldest entries when --entry-id is omitted.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List matching entries without changing either Stream.",
        )

    def handle(self, *args, **options):
        limit = int(options["limit"])
        if not 1 <= limit <= 1_000:
            raise CommandError("--limit must be between 1 and 1000")
        entry_ids = list(
            dict.fromkeys(
                str(value).strip() for value in options["entry_id"] if value
            )
        )
        if len(entry_ids) > 1_000:
            raise CommandError("at most 1000 --entry-id values may be supplied")

        client = redis_store.get_redis()
        if client is None:
            raise CommandError("Redis is unavailable")
        try:
            if entry_ids:
                rows = []
                for entry_id in entry_ids:
                    rows.extend(
                        client.xrange(
                            NODE_UPLINK_DEAD_LETTER_STREAM,
                            min=entry_id,
                            max=entry_id,
                            count=1,
                        )
                    )
            else:
                rows = client.xrange(
                    NODE_UPLINK_DEAD_LETTER_STREAM,
                    min="-",
                    max="+",
                    count=limit,
                )
        except RedisError as exc:
            raise CommandError(
                f"Unable to read Agent uplink dead letters: {type(exc).__name__}"
            ) from exc

        if not rows:
            self.stdout.write("No matching Agent uplink dead letters.")
            return

        failures = 0
        for entry_id, fields in rows:
            if options["dry_run"]:
                self.stdout.write(
                    f"would replay {entry_id} "
                    f"source_entry_id={fields.get('source_entry_id', 'unknown')}"
                )
                continue
            try:
                live_entry_id = replay_dead_letter_entry(
                    client,
                    entry_id=str(entry_id),
                    fields=fields,
                )
            except (RedisError, ValueError) as exc:
                failures += 1
                self.stderr.write(
                    f"failed {entry_id}: {type(exc).__name__}"
                )
                continue
            self.stdout.write(
                self.style.SUCCESS(
                    f"replayed {entry_id} as {live_entry_id}"
                )
            )

        if failures:
            raise CommandError(f"{failures} dead-letter replay(s) failed")
