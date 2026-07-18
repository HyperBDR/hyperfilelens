from django.urls import path

from apps.monitor.api.views import SystemMonitorView
from apps.monitor.api.views.node_monitor import NodeMonitorDetailView, NodeMonitorListView
from apps.monitor.api.views.platform_monitor import PlatformMonitorView
from apps.monitor.api.views.resource_monitor import ResourceMonitorView

urlpatterns = [
    path("system/", SystemMonitorView.as_view(), name="monitor-system"),
    path("resources/", ResourceMonitorView.as_view(), name="monitor-resources"),
    path("platform/", PlatformMonitorView.as_view(), name="monitor-platform"),
    path("nodes/", NodeMonitorListView.as_view(), name="monitor-nodes"),
    path("nodes/<int:node_id>/", NodeMonitorDetailView.as_view(), name="monitor-node-detail"),
]
