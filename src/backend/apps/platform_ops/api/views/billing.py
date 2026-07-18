"""Platform Ops billing APIs."""

from __future__ import annotations

from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.models import Organization
from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.serializers.platform import (
    PlatformPlanSerializer,
    PlatformQuotaPatchSerializer,
    PlatformQuotaUsageSerializer,
    PlatformSubscriptionSerializer,
)
from apps.platform_ops.api.views._utils import paginated, safe_int
from apps.platform_ops.services.internal.audit import write_platform_audit_log
from apps.subscription.models import License, OrganizationSubscription, Plan, Quota, UsageCounter
from apps.subscription.services.interface import get_or_create_machine_code


class PlatformOpsBillingPlansView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        rows = Plan.objects.order_by("key")
        return Response(PlatformPlanSerializer(rows, many=True).data)

    def post(self, request):
        serializer = PlatformPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = serializer.save()
        write_platform_audit_log(
            request=request,
            action="plan.create",
            target_type="plan",
            target_id=str(row.id),
            details={"key": row.key},
        )
        return Response(PlatformPlanSerializer(row).data, status=status.HTTP_201_CREATED)


class PlatformOpsBillingPlanDetailView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def patch(self, request, plan_id: int):
        row = Plan.objects.filter(pk=plan_id).first()
        if row is None:
            raise Http404
        serializer = PlatformPlanSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = serializer.save()
        write_platform_audit_log(
            request=request,
            action="plan.update",
            target_type="plan",
            target_id=str(row.id),
            details={"key": row.key},
        )
        return Response(PlatformPlanSerializer(row).data)


class PlatformOpsBillingSubscriptionsView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20, max_value=200)
        qs = OrganizationSubscription.objects.select_related("organization", "plan").order_by(
            "-updated_at",
        )
        org = request.query_params.get("org", "").strip()
        if org:
            qs = qs.filter(organization__key=org)
        total = qs.count()
        offset = (page - 1) * page_size
        rows = qs[offset : offset + page_size]
        return Response(
            paginated(
                PlatformSubscriptionSerializer(rows, many=True).data,
                total=total,
                page=page,
                page_size=page_size,
            )
        )

    def patch(self, request):
        sub_id = request.data.get("id")
        row = OrganizationSubscription.objects.filter(pk=sub_id).select_related("organization").first()
        if row is None:
            raise Http404
        serializer = PlatformSubscriptionSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = serializer.save()
        write_platform_audit_log(
            request=request,
            action="subscription.update",
            target_type="subscription",
            target_id=str(row.id),
            org_key=row.organization.key,
        )
        return Response(PlatformSubscriptionSerializer(row).data)


class PlatformOpsBillingQuotaUsageView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        org_key = request.query_params.get("org", "").strip()
        rows = []
        quotas = Quota.objects.select_related("organization")
        if org_key:
            quotas = quotas.filter(organization__key=org_key)
        counters = UsageCounter.objects.all()
        counter_map = {(c.organization_id, c.key, c.window): c.value for c in counters}
        for quota in quotas.order_by("organization__key", "key"):
            used = counter_map.get((quota.organization_id, quota.key, "lifetime"), 0)
            rows.append(
                {
                    "organization_id": quota.organization_id,
                    "organization_key": quota.organization.key,
                    "organization_name": quota.organization.name,
                    "key": quota.key,
                    "limit": quota.limit,
                    "unit": quota.unit,
                    "used": used,
                }
            )
        return Response(PlatformQuotaUsageSerializer(rows, many=True).data)

    def patch(self, request):
        serializer = PlatformQuotaPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        quota = Quota.objects.filter(
            organization_id=data["organization_id"],
            key=data["key"],
        ).select_related("organization").first()
        if quota is None:
            raise Http404
        quota.limit = data["limit"]
        quota.save(update_fields=["limit", "updated_at"])
        write_platform_audit_log(
            request=request,
            action="quota.update",
            target_type="quota",
            target_id=str(quota.id),
            org_key=quota.organization.key,
            details={"key": quota.key, "limit": quota.limit},
        )
        used = UsageCounter.objects.filter(
            organization_id=quota.organization_id,
            key=quota.key,
            window="lifetime",
        ).values_list("value", flat=True).first() or 0
        return Response(
            {
                "organization_id": quota.organization_id,
                "organization_key": quota.organization.key,
                "organization_name": quota.organization.name,
                "key": quota.key,
                "limit": quota.limit,
                "unit": quota.unit,
                "used": used,
            }
        )

class PlatformOpsBillingLicenseView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        org = Organization.objects.filter(is_active=True).order_by("id").first()
        license_row = None
        machine_code = None
        if org is not None:
            license_row = License.objects.filter(organization=org).first()
            machine_code = get_or_create_machine_code(organization=org, user=request.user)
        payload = {
            "organization_key": org.key if org else None,
            "organization_name": org.name if org else None,
            "machine_code": machine_code,
            "license": None,
        }
        if license_row is not None:
            payload["license"] = {
                "license_key": license_row.license_key,
                "status": license_row.status,
                "expires_at": license_row.expires_at,
                "activated_at": license_row.activated_at,
                "max_organizations": license_row.max_organizations,
                "max_users": license_row.max_users,
                "max_nodes": license_row.max_nodes,
                "max_storage_gb": license_row.max_storage_gb,
            }
        return Response(payload)
