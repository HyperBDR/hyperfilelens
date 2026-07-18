"""Periodic evaluation for metric, availability, and system alert policies."""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.alert.constants import AlertType, PolicyScope, ResourceType
from apps.alert.models import AlertPolicy, AlertRecord
from apps.alert.services.internal.lifecycle import fire_alert, resolve_alert
from apps.alert.services.internal.metadata_resources import resource_options
from apps.monitor.models import ResourceMetric, SystemMetric
from apps.monitor.services.internal.metric_values import (
    value_from_resource_metrics,
    value_from_system_metric,
)
from apps.monitor.services.internal.resource_metrics import latest_resource_metric
from apps.node.models import Node
from apps.node.models.base import NodeRole

logger = logging.getLogger(__name__)

_NODE_RESOURCE_BY_ROLE = {
    NodeRole.PROXY: ResourceType.SYNC_PROXY,
    NodeRole.AGENT: ResourceType.AGENT_PROXY,
    NodeRole.GATEWAY: ResourceType.GATEWAY,
}

_OPERATORS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def _policy_silenced(policy: AlertPolicy) -> bool:
    rule = policy.trigger_rule or {}
    until_raw = rule.get("silenced_until")
    if not until_raw:
        return False
    until = parse_datetime(str(until_raw))
    if until is None:
        return False
    if timezone.is_naive(until):
        until = timezone.make_aware(until, timezone.get_current_timezone())
    return timezone.now() < until


def _policy_resource_ids(policy: AlertPolicy) -> list[str]:
    if policy.scope == PolicyScope.ALL or policy.resource_type == ResourceType.SYSTEM:
        options = resource_options(
            organization_id=policy.organization_id,
            resource_type=policy.resource_type,
        )
        return [str(item["id"]) for item in options]
    return [str(rid) for rid in (policy.resource_ids or [])]


def _compare(operator: str, value: float, threshold: float) -> bool:
    fn = _OPERATORS.get(str(operator or ">").strip())
    if fn is None:
        fn = _OPERATORS[">"]
    return fn(value, threshold)


def _duration_satisfied(
    *,
    organization_id: int,
    resource_type: str,
    resource_id: str,
    metric_key: str,
    operator: str,
    threshold: float,
    duration_seconds: int,
) -> bool:
    duration = max(0, int(duration_seconds or 0))
    if duration <= 0:
        return True
    since = timezone.now() - timedelta(seconds=duration)
    samples = ResourceMetric.objects.filter(
        organization_id=organization_id,
        resource_type=resource_type,
        resource_id=str(resource_id),
        timestamp__gte=since,
    ).order_by("timestamp")
    if not samples.exists():
        return False
    for sample in samples:
        value = value_from_resource_metrics(sample.metrics or {}, metric_key)
        if value is None or not _compare(operator, value, threshold):
            return False
    return True


def _evaluate_metric_policy(policy: AlertPolicy) -> None:
    rule = policy.trigger_rule or {}
    metric_key = str(rule.get("metric_key") or "").strip()
    operator = str(rule.get("operator") or ">")
    threshold = float(rule.get("threshold") or 0)
    duration_seconds = int(rule.get("duration_seconds") or 0)
    if not metric_key:
        return

    for resource_id in _policy_resource_ids(policy):
        if policy.resource_type == ResourceType.SYSTEM:
            system = SystemMetric.objects.order_by("-timestamp").first()
            if system is None:
                continue
            value = value_from_system_metric(system, metric_key)
            resource_name = "Control Plane"
        else:
            sample = latest_resource_metric(
                organization_id=policy.organization_id,
                resource_type=policy.resource_type,
                resource_id=resource_id,
            )
            if sample is None:
                _maybe_resolve_metric(policy, resource_id)
                continue
            value = value_from_resource_metrics(sample.metrics or {}, metric_key)
            resource_name = sample.resource_name or resource_id
            if duration_seconds > 0 and not _duration_satisfied(
                organization_id=policy.organization_id,
                resource_type=policy.resource_type,
                resource_id=resource_id,
                metric_key=metric_key,
                operator=operator,
                threshold=threshold,
                duration_seconds=duration_seconds,
            ):
                _maybe_resolve_metric(policy, resource_id)
                continue

        if value is None:
            continue

        if _compare(operator, value, threshold):
            fire_alert(
                policy,
                resource=_ResourceStub(resource_id, resource_name),
                title=f"{policy.name}: {metric_key}",
                message=f"{metric_key}={value} {operator} {threshold}",
                current_value=value,
                alert_key=metric_key,
                metadata={"metric_key": metric_key, "value": value},
            )
        else:
            _maybe_resolve_metric(policy, resource_id)


def _maybe_resolve_metric(policy: AlertPolicy, resource_id: str) -> None:
    from apps.alert.constants import AlertStatus
    from apps.alert.services.internal.fingerprint import build_fingerprint

    metric_key = (policy.trigger_rule or {}).get("metric_key") or "default"
    fingerprint = build_fingerprint(policy, resource_id, str(metric_key))
    alert = AlertRecord.objects.filter(
        organization_id=policy.organization_id,
        fingerprint=fingerprint,
        status__in=[
            AlertStatus.PENDING,
            AlertStatus.FIRING,
            AlertStatus.ACKNOWLEDGED,
        ],
    ).first()
    if alert:
        resolve_alert(alert)


class _ResourceStub:
    def __init__(self, resource_id: str, name: str = ""):
        self.id = resource_id
        self.name = name


def _evaluate_availability_policy(policy: AlertPolicy) -> None:
    rule = policy.trigger_rule or {}
    check_type = str(rule.get("check_type") or "heartbeat")
    timeout_seconds = int(rule.get("timeout_seconds") or rule.get("duration_seconds") or 300)
    if check_type != "heartbeat":
        return

    now = timezone.now()
    for resource_id in _policy_resource_ids(policy):
        node = Node.objects.filter(
            organization_id=policy.organization_id,
            pk=resource_id,
        ).first()
        if node is None:
            continue
        expected_type = _NODE_RESOURCE_BY_ROLE.get(node.role)
        if expected_type and policy.resource_type != expected_type:
            continue
        last_seen = node.last_seen_at
        stale = last_seen is None or (now - last_seen).total_seconds() > timeout_seconds
        stub = _ResourceStub(str(node.id), node.name)
        if stale or node.status != Node.Status.ONLINE:
            fire_alert(
                policy,
                resource=stub,
                title=f"{policy.name}: node unavailable",
                message=f"Node {node.name} last seen {last_seen}",
                current_value=Decimal(str(int((now - last_seen).total_seconds()) if last_seen else timeout_seconds + 1)),
                alert_key=check_type,
                metadata={"check_type": check_type, "node_status": node.status},
            )
        else:
            _maybe_resolve_metric(policy, str(node.id))


def _evaluate_system_policy(policy: AlertPolicy) -> None:
    rule = policy.trigger_rule or {}
    check_type = str(rule.get("check_type") or "service_health")
    if check_type == "disk_space_low":
        policy.trigger_rule = {
            **rule,
            "metric_key": "disk_usage",
            "operator": ">=",
            "threshold": rule.get("threshold", 90),
            "duration_seconds": rule.get("duration_seconds", 0),
        }
        _evaluate_metric_policy(policy)
        return
    # service_health: rely on latest system metric CPU/memory thresholds if set
    if rule.get("metric_key"):
        _evaluate_metric_policy(policy)


def evaluate_organization_policies(*, organization_id: int | None = None) -> dict:
    qs = AlertPolicy.objects.filter(enabled=True).exclude(type=AlertType.TASK).exclude(
        type=AlertType.EVENT
    )
    if organization_id is not None:
        qs = qs.filter(organization_id=organization_id)

    counts = {"metric": 0, "availability": 0, "system": 0, "skipped": 0}
    for policy in qs.iterator():
        if _policy_silenced(policy):
            counts["skipped"] += 1
            continue
        try:
            if policy.type == AlertType.METRIC:
                _evaluate_metric_policy(policy)
                counts["metric"] += 1
            elif policy.type == AlertType.AVAILABILITY:
                _evaluate_availability_policy(policy)
                counts["availability"] += 1
            elif policy.type == AlertType.SYSTEM:
                _evaluate_system_policy(policy)
                counts["system"] += 1
        except Exception:
            logger.exception("alert evaluation failed policy=%s", policy.id)
    return counts


def evaluate_all_policies() -> dict:
    return evaluate_organization_policies()
