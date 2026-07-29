"""Public signed callback used by detached Agent uninstall runners."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.node.services.internal.uninstall_completion import (
    UninstallCompletionError,
    complete_detached_uninstall,
)


class AgentUninstallCompletionView(APIView):
    """Accept a one-time signed completion result after the Agent stops."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        cleanup_complete = data.get("cleanup_complete")
        if not isinstance(cleanup_complete, bool):
            return Response(
                {
                    "detail": "cleanup_complete must be a boolean.",
                    "code": "invalid_uninstall_completion",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            outcome = complete_detached_uninstall(
                token=str(data.get("token") or ""),
                cleanup_complete=cleanup_complete,
                cleanup_failures=(
                    data.get("cleanup_failures")
                    if isinstance(data.get("cleanup_failures"), list)
                    else []
                ),
                retained_resources=(
                    data.get("retained_resources")
                    if isinstance(data.get("retained_resources"), list)
                    else []
                ),
            )
        except UninstallCompletionError as exc:
            return Response(
                {"detail": str(exc), "code": "invalid_uninstall_completion"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(outcome.to_payload(), status=status.HTTP_200_OK)
