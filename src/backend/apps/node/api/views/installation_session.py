"""Create resumable installation sessions from enrollment tokens."""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.models import Organization
from apps.node.api import permissions as node_permissions
from apps.node.models import Node
from apps.node.services.internal.enrollment_auth import (
    open_installation_session,
    release_installation_session,
)
from common.http.throttling import EnrollmentRateThrottle


class InstallationSessionView(APIView):
    """Reserve one host slot and exchange an enrollment token for a session."""

    permission_classes = [node_permissions.AllowAny]
    throttle_classes = [EnrollmentRateThrottle]

    @staticmethod
    def _request_identity(request):
        payload = request.data if isinstance(request.data, dict) else {}
        return (
            str(request.headers.get("X-Org-Key", "") or "").strip(),
            str(request.headers.get("X-Node-Token", "") or "").strip(),
            str(payload.get("role") or request.query_params.get("role") or "").strip(),
            str(
                payload.get("installation_id")
                or request.query_params.get("installation_id")
                or ""
            ).strip(),
        )

    def post(self, request):
        org_key, enrollment_secret, role, installation_id = self._request_identity(
            request
        )
        if not org_key or not enrollment_secret or not installation_id:
            return Response(
                {
                    "error": (
                        "X-Org-Key, X-Node-Token, and installation_id are required"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(installation_id) > 128:
            return Response(
                {"error": "installation_id must not exceed 128 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if role not in dict(Node.Role.choices):
            return Response(
                {"error": "invalid role"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        org = Organization.objects.filter(key=org_key, is_active=True).first()
        if org is None:
            return Response(
                {"error": "organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            session, secret = open_installation_session(
                org=org,
                enrollment_secret=enrollment_secret,
                role=role,
                installation_id=installation_id,
            )
        except PermissionError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "installation_session": secret,
                "gateway_scope": (
                    "public"
                    if session.enrollment_token.gateway_scope == "platform"
                    else "private"
                )
                if role == Node.Role.GATEWAY
                else "",
                "idle_expires_at": session.idle_expires_at,
                "absolute_expires_at": session.absolute_expires_at,
            },
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        """Release an active reservation when the installer exits before registration."""
        org_key, session_secret, role, installation_id = self._request_identity(request)
        if not org_key or not session_secret or not role or not installation_id:
            return Response(
                {
                    "error": (
                        "X-Org-Key, X-Node-Token, role, and installation_id "
                        "are required"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(installation_id) > 128:
            return Response(
                {"error": "installation_id must not exceed 128 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if role not in dict(Node.Role.choices):
            return Response(
                {"error": "invalid role"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        org = Organization.objects.filter(key=org_key, is_active=True).first()
        if org is None:
            return Response(
                {"error": "organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        released = release_installation_session(
            org=org,
            secret=session_secret,
            role=role,
            installation_id=installation_id,
        )
        if not released:
            return Response(
                {"error": "active installation session not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
