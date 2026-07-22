from django.urls import path

from apps.platform_ops.api.views.billing import (
    PlatformOpsBillingLicenseView,
    PlatformOpsBillingPlanDetailView,
    PlatformOpsBillingPlansView,
    PlatformOpsBillingQuotaUsageView,
    PlatformOpsBillingSubscriptionsView,
)
from apps.platform_ops.api.views.monitoring import (
    PlatformOpsMonitoringAlertsView,
    PlatformOpsMonitoringHostView,
    PlatformOpsMonitoringHostsView,
    PlatformOpsMonitoringNodesView,
    PlatformOpsMonitoringNotificationsView,
    PlatformOpsMonitoringTasksView,
)
from apps.platform_ops.api.views.orgs import (
    PlatformOpsOrganizationDetailView,
    PlatformOpsOrganizationListView,
    PlatformOpsOrganizationSummaryView,
)
from apps.platform_ops.api.views.lens import (
    PlatformOpsLensAssistantFormOptionsView,
    PlatformOpsLensAssistantView,
    PlatformOpsLensGatewayBrowseView,
    PlatformOpsLensGatewayEnableAiView,
    PlatformOpsLensGatewayEnrollmentView,
    PlatformOpsLensGatewayListView,
    PlatformOpsLensGatewayLifecycleWatchView,
    PlatformOpsLensGatewayOperationBatchView,
    PlatformOpsLensGatewayOperationPreviewView,
    PlatformOpsLensGatewayOperationView,
    PlatformOpsLensGatewaySetDefaultView,
    PlatformOpsLensKnowledgeSourceSyncView,
    PlatformOpsLensKnowledgeSourceView,
    PlatformOpsLensMcpServerView,
    PlatformOpsLensModelProxyView,
    PlatformOpsLensSkillView,
)
from apps.platform_ops.api.views.overview import PlatformOpsOverviewView
from apps.platform_ops.api.views.platform import (
    PlatformOpsPlatformAgentReleasesView,
    PlatformOpsPlatformNotificationChannelsView,
)
from apps.platform_ops.api.views.platform_settings import (
    PlatformOpsBillingLicenseActivateView,
    PlatformOpsSettingsAiTestView,
    PlatformOpsSettingsAiView,
    PlatformOpsSettingsDefaultsView,
    PlatformOpsSettingsEmailTestView,
    PlatformOpsSettingsEmailView,
    PlatformOpsSettingsEnvironmentView,
    PlatformOpsSettingsIdentityView,
)
from apps.platform_ops.api.views.staff_activity import PlatformOpsStaffActivityView
from apps.platform_ops.api.views.support import PlatformOpsSupportSessionView
from apps.platform_ops.api.views.system import (
    PlatformOpsSystemAuditView,
    PlatformOpsSystemDatabaseView,
    PlatformOpsSystemHealthView,
)
from apps.platform_ops.api.views.users import (
    PlatformOpsUserDetailView,
    PlatformOpsUserListCreateView,
    PlatformOpsUserResetPasswordView,
)

urlpatterns = [
    path("", PlatformOpsOverviewView.as_view(), name="platform-ops-overview"),
    path("users", PlatformOpsUserListCreateView.as_view(), name="platform-ops-users"),
    path(
        "users/<int:user_id>",
        PlatformOpsUserDetailView.as_view(),
        name="platform-ops-user-detail",
    ),
    path(
        "users/<int:user_id>/reset-password",
        PlatformOpsUserResetPasswordView.as_view(),
        name="platform-ops-user-reset-password",
    ),
    path("orgs", PlatformOpsOrganizationListView.as_view(), name="platform-ops-orgs"),
    path(
        "orgs/<int:org_id>",
        PlatformOpsOrganizationDetailView.as_view(),
        name="platform-ops-org-detail",
    ),
    path(
        "orgs/<int:org_id>/summary",
        PlatformOpsOrganizationSummaryView.as_view(),
        name="platform-ops-org-summary",
    ),
    path(
        "orgs/<int:org_id>/support-session",
        PlatformOpsSupportSessionView.as_view(),
        name="platform-ops-support-session",
    ),
    path("staff-activity", PlatformOpsStaffActivityView.as_view(), name="platform-ops-staff-activity"),
    path("monitoring/alerts", PlatformOpsMonitoringAlertsView.as_view(), name="platform-ops-monitoring-alerts"),
    path("monitoring/tasks", PlatformOpsMonitoringTasksView.as_view(), name="platform-ops-monitoring-tasks"),
    path("monitoring/nodes", PlatformOpsMonitoringNodesView.as_view(), name="platform-ops-monitoring-nodes"),
    path(
        "monitoring/notifications",
        PlatformOpsMonitoringNotificationsView.as_view(),
        name="platform-ops-monitoring-notifications",
    ),
    path("monitoring/hosts", PlatformOpsMonitoringHostsView.as_view(), name="platform-ops-monitoring-hosts"),
    path("monitoring/host", PlatformOpsMonitoringHostView.as_view(), name="platform-ops-monitoring-host"),
    path("platform/settings/email", PlatformOpsSettingsEmailView.as_view(), name="platform-ops-settings-email"),
    path(
        "platform/settings/email/test",
        PlatformOpsSettingsEmailTestView.as_view(),
        name="platform-ops-settings-email-test",
    ),
    path(
        "platform/settings/identity",
        PlatformOpsSettingsIdentityView.as_view(),
        name="platform-ops-settings-identity",
    ),
    path("platform/settings/ai", PlatformOpsSettingsAiView.as_view(), name="platform-ops-settings-ai"),
    path(
        "platform/settings/ai/test",
        PlatformOpsSettingsAiTestView.as_view(),
        name="platform-ops-settings-ai-test",
    ),
    path(
        "platform/settings/defaults",
        PlatformOpsSettingsDefaultsView.as_view(),
        name="platform-ops-settings-defaults",
    ),
    path(
        "platform/settings/environment",
        PlatformOpsSettingsEnvironmentView.as_view(),
        name="platform-ops-settings-environment",
    ),
    path(
        "platform/agent-releases",
        PlatformOpsPlatformAgentReleasesView.as_view(),
        name="platform-ops-platform-agent-releases",
    ),
    path(
        "platform/notification-channels",
        PlatformOpsPlatformNotificationChannelsView.as_view(),
        name="platform-ops-platform-notification-channels",
    ),
    path("billing/plans", PlatformOpsBillingPlansView.as_view(), name="platform-ops-billing-plans"),
    path(
        "billing/plans/<int:plan_id>",
        PlatformOpsBillingPlanDetailView.as_view(),
        name="platform-ops-billing-plan-detail",
    ),
    path(
        "billing/subscriptions",
        PlatformOpsBillingSubscriptionsView.as_view(),
        name="platform-ops-billing-subscriptions",
    ),
    path(
        "billing/quota-usage",
        PlatformOpsBillingQuotaUsageView.as_view(),
        name="platform-ops-billing-quota-usage",
    ),
    path("billing/license", PlatformOpsBillingLicenseView.as_view(), name="platform-ops-billing-license"),
    path(
        "billing/license/activate",
        PlatformOpsBillingLicenseActivateView.as_view(),
        name="platform-ops-billing-license-activate",
    ),
    path("system/health", PlatformOpsSystemHealthView.as_view(), name="platform-ops-system-health"),
    path(
        "system/database",
        PlatformOpsSystemDatabaseView.as_view(),
        name="platform-ops-system-database",
    ),
    path("system/audit", PlatformOpsSystemAuditView.as_view(), name="platform-ops-system-audit"),
    path("lens/gateways", PlatformOpsLensGatewayListView.as_view(), name="platform-ops-lens-gateways"),
    path(
        "lens/gateways/enrollment",
        PlatformOpsLensGatewayEnrollmentView.as_view(),
        name="platform-ops-lens-gateway-enrollment",
    ),
    path(
        "lens/gateways/<int:gateway_id>/enable-ai",
        PlatformOpsLensGatewayEnableAiView.as_view(),
        name="platform-ops-lens-gateway-enable-ai",
    ),
    path(
        "lens/gateways/<int:gateway_id>/set-default",
        PlatformOpsLensGatewaySetDefaultView.as_view(),
        name="platform-ops-lens-gateway-set-default",
    ),
    path(
        "lens/gateways/<int:gateway_id>/operations",
        PlatformOpsLensGatewayOperationView.as_view(),
        name="platform-ops-lens-gateway-operation",
    ),
    path(
        "lens/gateways/operations/preview",
        PlatformOpsLensGatewayOperationPreviewView.as_view(),
        name="platform-ops-lens-gateway-operation-preview",
    ),
    path(
        "lens/gateways/operations/batch",
        PlatformOpsLensGatewayOperationBatchView.as_view(),
        name="platform-ops-lens-gateway-operation-batch",
    ),
    path(
        "lens/gateways/lifecycle-watch",
        PlatformOpsLensGatewayLifecycleWatchView.as_view(),
        name="platform-ops-lens-gateway-lifecycle-watch",
    ),
    path(
        "lens/gateways/<int:gateway_id>/browse",
        PlatformOpsLensGatewayBrowseView.as_view(),
        name="platform-ops-lens-gateway-browse",
    ),
    path(
        "lens/knowledge-sources",
        PlatformOpsLensKnowledgeSourceView.as_view(),
        name="platform-ops-lens-knowledge-sources",
    ),
    path(
        "lens/knowledge-sources/<int:ks_id>",
        PlatformOpsLensKnowledgeSourceView.as_view(),
        name="platform-ops-lens-knowledge-sources-detail",
    ),
    path(
        "lens/knowledge-sources/<int:ks_id>/sync",
        PlatformOpsLensKnowledgeSourceSyncView.as_view(),
        name="platform-ops-lens-knowledge-sources-sync",
    ),
    path("lens/models", PlatformOpsLensModelProxyView.as_view(), name="platform-ops-lens-models-list"),
    path(
        "lens/models/providers",
        PlatformOpsLensModelProxyView.as_view(),
        name="platform-ops-lens-models-providers",
    ),
    path(
        "lens/models/catalog",
        PlatformOpsLensModelProxyView.as_view(),
        name="platform-ops-lens-models-catalog",
    ),
    path("lens/models/test", PlatformOpsLensModelProxyView.as_view(), name="platform-ops-lens-models-test"),
    path(
        "lens/models/<uuid:config_uuid>",
        PlatformOpsLensModelProxyView.as_view(),
        name="platform-ops-lens-models-detail",
    ),
    path(
        "lens/models/<uuid:config_uuid>/test-call",
        PlatformOpsLensModelProxyView.as_view(),
        name="platform-ops-lens-models-test-call",
    ),
    path("lens/assistants", PlatformOpsLensAssistantView.as_view(), name="platform-ops-lens-assistants"),
    path(
        "lens/assistants/form-options",
        PlatformOpsLensAssistantFormOptionsView.as_view(),
        name="platform-ops-lens-assistants-form-options",
    ),
    path(
        "lens/assistants/<uuid:assistant_uuid>",
        PlatformOpsLensAssistantView.as_view(),
        name="platform-ops-lens-assistants-detail",
    ),
    path("lens/skills", PlatformOpsLensSkillView.as_view(), name="platform-ops-lens-skills"),
    path(
        "lens/skills/beautify",
        PlatformOpsLensSkillView.as_view(),
        name="platform-ops-lens-skills-beautify",
    ),
    path(
        "lens/skills/<uuid:skill_uuid>",
        PlatformOpsLensSkillView.as_view(),
        name="platform-ops-lens-skills-detail",
    ),
    path("lens/mcp-servers", PlatformOpsLensMcpServerView.as_view(), name="platform-ops-lens-mcp-servers"),
    path(
        "lens/mcp-servers/<uuid:mcp_uuid>",
        PlatformOpsLensMcpServerView.as_view(),
        name="platform-ops-lens-mcp-servers-detail",
    ),
]
