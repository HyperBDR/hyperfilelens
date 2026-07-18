"""REST routes for nodes, tokens, tasks, and enrollment."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.node.api.views import (
    AgentLatestReleaseView,
    AgentReleaseView,
    AgentReleasesAuthView,
    BootstrapGatewayView,
    BootstrapView,
    EnrollmentTokenCreateView,
    GatewayInstallStatusView,
    GatewayLensConfigView,
    NodeOperationBatchPreviewView,
    NodeOperationBatchStartView,
    NodeTaskViewSet,
    NodeTokenViewSet,
    NodeViewSet,
    enrollment_health,
    health,
)

router = DefaultRouter()
router.register(r"nodes", NodeViewSet, basename="node")
router.register(r"node-tokens", NodeTokenViewSet, basename="node-token")
router.register(r"node-tasks", NodeTaskViewSet, basename="node-task")

urlpatterns = [
    path("health", health, name="node-health"),
    path("enrollment/health", enrollment_health, name="enrollment-health"),
    path(
        "enrollment/enrollment-token",
        EnrollmentTokenCreateView.as_view(),
        name="enrollment-token-create",
    ),
    path(
        "enrollment/bootstrap",
        BootstrapView.as_view(),
        name="enrollment-bootstrap",
    ),
    path(
        "enrollment/bootstrap-gateway",
        BootstrapGatewayView.as_view(),
        name="enrollment-bootstrap-gateway",
    ),
    path(
        "enrollment/gateway-lens-config",
        GatewayLensConfigView.as_view(),
        name="enrollment-gateway-lens-config",
    ),
    path(
        "enrollment/gateway-install-status",
        GatewayInstallStatusView.as_view(),
        name="enrollment-gateway-install-status",
    ),
    path(
        "agent-release/latest",
        AgentLatestReleaseView.as_view(),
        name="agent-release-latest",
    ),
    path(
        "enrollment/agent/release",
        AgentReleaseView.as_view(),
        name="enrollment-agent-release",
    ),
    path(
        "enrollment/agent-releases/auth",
        AgentReleasesAuthView.as_view(),
        name="enrollment-agent-releases-auth",
    ),
    path(
        "nodes/operations/preview/",
        NodeOperationBatchPreviewView.as_view(),
        name="node-operations-preview",
    ),
    path(
        "nodes/operations/batch/",
        NodeOperationBatchStartView.as_view(),
        name="node-operations-batch",
    ),
    path("", include(router.urls)),
]
