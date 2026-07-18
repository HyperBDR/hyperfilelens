"""Organization resource summary for Platform Ops."""

from __future__ import annotations

from apps.iam.models import Membership, Organization


def organization_resource_summary(org: Organization) -> dict:
    counts = {
        "members": Membership.objects.filter(organization=org, is_active=True).count(),
        "nodes": 0,
        "tasks_running": 0,
        "tasks_failed": 0,
        "alerts_firing": 0,
    }
    try:
        from apps.node.models import Node

        counts["nodes"] = Node.objects.filter(organization=org).count()
    except Exception:
        pass
    try:
        from apps.task.models import Task

        counts["tasks_running"] = Task.objects.filter(
            organization=org,
            status=Task.Status.RUNNING,
        ).count()
        counts["tasks_failed"] = Task.objects.filter(
            organization=org,
            status__in=[Task.Status.FAILED, Task.Status.TIMEOUT],
        ).count()
    except Exception:
        pass
    try:
        from apps.alert.constants import AlertStatus
        from apps.alert.models import AlertRecord

        counts["alerts_firing"] = AlertRecord.objects.filter(
            organization=org,
            status=AlertStatus.FIRING,
        ).count()
    except Exception:
        pass
    usage = []
    try:
        from apps.subscription.models import Quota, UsageCounter

        quotas = Quota.objects.filter(organization=org)
        counters = {
            (row.key, row.window): row.value
            for row in UsageCounter.objects.filter(organization=org)
        }
        for quota in quotas:
            usage.append(
                {
                    "key": quota.key,
                    "limit": quota.limit,
                    "unit": quota.unit,
                    "used": counters.get((quota.key, "lifetime"), 0),
                }
            )
    except Exception:
        pass

    subscription = None
    license_info = None
    try:
        from apps.subscription.models import License, OrganizationSubscription

        sub = (
            OrganizationSubscription.objects.filter(organization=org)
            .select_related("plan")
            .order_by("-updated_at")
            .first()
        )
        if sub is not None:
            subscription = {
                "id": sub.id,
                "plan_key": sub.plan.key if sub.plan_id else "",
                "plan_name": sub.plan.name if sub.plan_id else "",
                "status": sub.status,
                "started_at": sub.started_at,
                "ends_at": sub.ends_at,
            }
        lic = License.objects.filter(organization=org).first()
        if lic is not None:
            license_info = {
                "license_key": lic.license_key,
                "status": lic.status,
                "expires_at": lic.expires_at,
                "activated_at": lic.activated_at,
            }
    except Exception:
        pass

    return {
        "counts": counts,
        "quota_usage": usage,
        "subscription": subscription,
        "license": license_info,
    }
