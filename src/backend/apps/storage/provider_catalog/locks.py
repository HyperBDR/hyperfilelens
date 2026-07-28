"""Stable per-Provider transaction locks shared by all Catalog write paths."""

from __future__ import annotations

import hashlib

from django.db import connection

from apps.storage.provider_catalog.models import StorageProviderOverride


def lock_provider_ids(provider_ids: list[str]) -> None:
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            for provider_id in sorted(provider_ids):
                digest = hashlib.sha256(
                    f"storage-provider:{provider_id}".encode("utf-8")
                ).digest()
                lock_id = int.from_bytes(digest[:8], byteorder="big", signed=True)
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
    list(
        StorageProviderOverride.objects.select_for_update()
        .filter(provider_id__in=provider_ids)
        .order_by("provider_id")
    )
