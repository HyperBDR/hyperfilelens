"""Alert policy evaluation tests."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.alert.constants import AlertType, ResourceType
from apps.alert.models import AlertPolicy, AlertRecord
from apps.alert.services.internal.evaluation import evaluate_organization_policies
from apps.iam.models import Organization
from apps.monitor.services.internal.resource_metrics import record_resource_metric
from apps.node.models import Node
from apps.node.models.base import NodeRole


@pytest.mark.django_db
def test_metric_policy_fires_on_high_cpu(db):
    org = Organization.objects.create(key="eval-org", name="Eval Org")
    policy = AlertPolicy.objects.create(
        organization=org,
        name="CPU",
        type=AlertType.METRIC,
        severity="warning",
        enabled=True,
        resource_type=ResourceType.SYNC_PROXY,
        scope="selected",
        resource_ids=["1"],
        trigger_rule={
            "metric_key": "cpu_usage",
            "operator": ">",
            "threshold": 80,
            "duration_seconds": 0,
            "evaluation_interval_seconds": 60,
        },
    )
    record_resource_metric(
        organization_id=org.id,
        resource_type=ResourceType.SYNC_PROXY,
        resource_id="1",
        metrics={"cpu_usage": 95},
        resource_name="proxy-1",
    )
    result = evaluate_organization_policies(organization_id=org.id)
    assert result["metric"] == 1
    assert AlertRecord.objects.filter(organization=org, policy_id=policy.id).exists()


@pytest.mark.django_db
def test_availability_policy_fires_on_stale_node(db):
    org = Organization.objects.create(key="eval-org-2", name="Eval Org 2")
    node = Node.objects.create(
        organization=org,
        name="stale-node",
        role=NodeRole.PROXY,
        status=Node.Status.OFFLINE,
        last_seen_at=timezone.now() - timedelta(hours=2),
    )
    AlertPolicy.objects.create(
        organization=org,
        name="Heartbeat",
        type=AlertType.AVAILABILITY,
        severity="critical",
        enabled=True,
        resource_type=ResourceType.SYNC_PROXY,
        scope="selected",
        resource_ids=[str(node.id)],
        trigger_rule={"check_type": "heartbeat", "timeout_seconds": 300},
    )
    evaluate_organization_policies(organization_id=org.id)
    assert AlertRecord.objects.filter(organization=org, resource_id=str(node.id)).exists()
