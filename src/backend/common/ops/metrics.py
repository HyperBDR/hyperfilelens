from __future__ import annotations

import os

from django.http import HttpResponse


def metrics(_request) -> HttpResponse:
    """
    Prometheus metrics endpoint.

    Enabled only when ENABLE_METRICS=true. Otherwise returns 404 to avoid
    accidental exposure.
    """

    enabled = os.getenv("ENABLE_METRICS", "").strip().lower() in ("1", "true", "yes", "on")
    if not enabled:
        return HttpResponse(status=404)

    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    except Exception:
        return HttpResponse(status=501)

    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)

