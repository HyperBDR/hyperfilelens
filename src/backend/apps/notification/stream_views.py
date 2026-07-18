"""HTTP helpers for notification domain (no WebSocket; see apps.node for WS)."""

from django.http import JsonResponse


def stream_health(_request):
    return JsonResponse({"app": "notification", "stream": "live", "status": "ok"})
