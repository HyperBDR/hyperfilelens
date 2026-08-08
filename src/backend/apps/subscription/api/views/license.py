"""
License management API (xxz-aligned, organization-scoped).
"""

from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.constants import AuditAction, AuditResult
from apps.audit.services.interface import write_audit_log
from apps.iam.permissions_org import IsOrgAdmin, IsOrgMember, get_membership
from apps.subscription.api.serializers import (
    ActivateLicenseSerializer,
    LicenseHistorySerializer,
    LicenseSerializer,
)
from apps.subscription.models import License, LicenseHistory
from apps.subscription.services.interface import (
    activate_license,
    build_current_payload,
    get_or_create_machine_code,
    validate_quota,
)


def health(_request):
    return JsonResponse({"app": "subscription", "status": "ok"})


def _require_org(request):
    membership = get_membership(request)
    if membership is None:
        return None
    return membership.organization


class LicenseViewSet(viewsets.GenericViewSet):
    """License endpoints at /api/v1/subscription/licenses/."""

    permission_classes = [IsAuthenticated, IsOrgMember]
    queryset = License.objects.none()

    def get_permissions(self):
        # Activate / regenerate machine code: owner+admin when AuthzProvider is live;
        # community (no provider) treats every active affiliation as OWNER.
        if getattr(self, "action", None) == "activate":
            return [IsAuthenticated(), IsOrgAdmin()]
        if getattr(self, "action", None) == "machine_code" and self.request.method == "POST":
            return [IsAuthenticated(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrgMember()]

    def _org(self, request):
        return _require_org(request)

    @action(detail=False, methods=["get"])
    def current(self, request):
        org = self._org(request)
        if org is None:
            return Response({"detail": "Organization required"}, status=status.HTTP_400_BAD_REQUEST)
        payload = build_current_payload(organization=org, user=request.user)
        lic = payload.get("license")
        data = {
            "is_valid": payload["is_valid"],
            "message": payload.get("message", ""),
            "machine_code": payload["machine_code"],
            "usage": payload["usage"],
            "limits": payload.get("limits"),
            "days_until_expiry": payload.get("days_until_expiry"),
            "enforcement_enabled": payload.get("enforcement_enabled", False),
            "organization_name": payload.get("organization_name") or org.name,
            "instance_shared": bool(payload.get("instance_shared")),
        }
        if lic:
            data["license"] = LicenseSerializer(lic).data
            if data["instance_shared"]:
                # Secondary tenants must not see host grant secrets / identity.
                for key in (
                    "license_key",
                    "organization",
                    "organization_name",
                    "organization_key",
                    "machine_code",
                    "signature",
                    "max_organizations",
                    "max_users",
                    "max_nodes",
                    "max_storage_gb",
                    "max_gateways",
                    "ai_insights_quota",
                    "max_tasks",
                    "max_alert_policies",
                ):
                    data["license"].pop(key, None)
        return Response(data)

    @action(detail=False, methods=["get", "post"], url_path="machine_code")
    def machine_code(self, request):
        org = self._org(request)
        if org is None:
            return Response({"detail": "Organization required"}, status=status.HTTP_400_BAD_REQUEST)
        force = request.method == "POST"
        code = get_or_create_machine_code(organization=org, user=request.user, force=force)
        return Response(
            {
                "machine_code": code,
                "organization_name": org.name,
                "message": "Machine code regenerated" if force else "Machine code",
            }
        )

    @action(detail=False, methods=["post"])
    def activate(self, request):
        org = self._org(request)
        if org is None:
            return Response({"detail": "Organization required"}, status=status.HTTP_400_BAD_REQUEST)
        ser = ActivateLicenseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            lic, change_type = activate_license(
                organization=org,
                user=request.user,
                activation_code=ser.validated_data["activation_code"],
            )
            write_audit_log(
                organization=org,
                user=request.user,
                action=AuditAction.UPDATE,
                resource_type="license",
                resource_id=str(lic.id),
                resource_name=lic.license_key[:32],
                result=AuditResult.SUCCESS,
                details=f"license.activate:{change_type}",
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=str(request.META.get("HTTP_USER_AGENT", "") or ""),
            )
            return Response(
                {
                    "success": True,
                    "change_type": change_type,
                    "license": LicenseSerializer(lic).data,
                }
            )
        except ValueError as exc:
            write_audit_log(
                organization=org,
                user=request.user,
                action=AuditAction.UPDATE,
                resource_type="license",
                result=AuditResult.FAILURE,
                error_message=str(exc),
                details="license.activate",
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            return Response(
                {"error": "invalid_activation_code", "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def history(self, request):
        org = self._org(request)
        if org is None:
            return Response({"detail": "Organization required"}, status=status.HTTP_400_BAD_REQUEST)
        rows = LicenseHistory.objects.filter(organization=org).order_by("-archived_at")[:100]
        return Response(
            {
                "count": rows.count(),
                "results": LicenseHistorySerializer(rows, many=True).data,
            }
        )

    @action(detail=False, methods=["get"])
    def validate(self, request):
        org = self._org(request)
        if org is None:
            return Response({"detail": "Organization required"}, status=status.HTTP_400_BAD_REQUEST)
        quota_type = (request.query_params.get("quota_type") or "").strip()
        amount = int(request.query_params.get("amount") or 1)
        if not quota_type:
            return Response(
                {"error": "missing_quota_type", "message": "quota_type is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(validate_quota(org, quota_type, amount))
