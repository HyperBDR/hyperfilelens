"""Platform Ops staff support session into tenant context."""

from __future__ import annotations

from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.models import Organization
from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.constants import SUPPORT_SESSION_KEY
from apps.platform_ops.services.internal.audit import write_platform_audit_log
from common.deploy.site import tenant_public_url


class PlatformOpsSupportSessionView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request, org_id: int):
        org = Organization.objects.filter(pk=org_id, is_active=True).first()
        if org is None:
            raise Http404
        request.session[SUPPORT_SESSION_KEY] = org.key
        write_platform_audit_log(
            request=request,
            action="support.enter",
            target_type="organization",
            target_id=str(org.id),
            org_key=org.key,
        )
        return Response(
            {
                "org_key": org.key,
                "org_name": org.name,
                "tenant_url": tenant_public_url(),
            }
        )

    def delete(self, request, org_id: int):
        org = Organization.objects.filter(pk=org_id).first()
        if org is None:
            raise Http404
        if request.session.get(SUPPORT_SESSION_KEY) == org.key:
            request.session.pop(SUPPORT_SESSION_KEY, None)
        write_platform_audit_log(
            request=request,
            action="support.exit",
            target_type="organization",
            target_id=str(org.id),
            org_key=org.key,
        )
        return Response({"ok": True})
