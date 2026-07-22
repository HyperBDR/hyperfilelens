import { lazyRoute } from '../router/lazyRoute'

export const platformOpsRoutes = [
  { path: '', redirect: '/platform-ops/overview' },
  {
    path: 'overview',
    name: 'PlatformOpsOverview',
    component: lazyRoute(() => import('./pages/overview/Overview.vue')),
  },
  {
    path: 'users',
    name: 'PlatformOpsUsers',
    component: lazyRoute(() => import('./pages/users/UserList.vue')),
  },
  {
    path: 'users/:id',
    name: 'PlatformOpsUserDetail',
    component: lazyRoute(() => import('./pages/users/UserDetail.vue')),
  },
  {
    path: 'orgs',
    name: 'PlatformOpsOrgs',
    component: lazyRoute(() => import('./pages/orgs/OrgList.vue')),
  },
  {
    path: 'orgs/:id',
    name: 'PlatformOpsOrgDetail',
    component: lazyRoute(() => import('./pages/orgs/OrgDetail.vue')),
  },
  {
    path: 'monitoring/monitor',
    name: 'PlatformOpsMonitoringMonitor',
    component: lazyRoute(() => import('./pages/monitoring/MonitoringHost.vue')),
  },
  { path: 'monitoring/system-health', redirect: '/platform-ops/monitoring/monitor' },
  { path: 'monitoring/host', redirect: '/platform-ops/monitoring/monitor' },
  {
    path: 'monitoring/tasks',
    name: 'PlatformOpsMonitoringTasks',
    component: lazyRoute(() => import('./pages/monitoring/MonitoringTasks.vue')),
  },
  {
    path: 'monitoring/nodes',
    name: 'PlatformOpsMonitoringNodes',
    component: lazyRoute(() => import('./pages/monitoring/MonitoringNodes.vue')),
  },
  {
    path: 'monitoring/logs',
    name: 'PlatformOpsMonitoringLogs',
    component: lazyRoute(() => import('./pages/monitoring/MonitoringLogs.vue')),
  },
  {
    path: 'alert-center/incidents',
    name: 'PlatformOpsAlertCenterIncidents',
    component: lazyRoute(() => import('./pages/monitoring/MonitoringIncidents.vue')),
  },
  {
    path: 'alert-center/policies',
    name: 'PlatformOpsAlertCenterPolicies',
    component: lazyRoute(() => import('./pages/alert-center/AlertPolicies.vue')),
  },
  {
    path: 'alert-center/notification-channels',
    name: 'PlatformOpsAlertCenterNotificationChannels',
    component: lazyRoute(() => import('./pages/alert-center/NotificationChannels.vue')),
  },
  {
    path: 'alert-center/notification-history',
    name: 'PlatformOpsAlertCenterNotificationHistory',
    component: lazyRoute(() => import('./pages/monitoring/MonitoringDeliveries.vue')),
  },
  { path: 'monitoring/incidents', redirect: '/platform-ops/alert-center/incidents' },
  { path: 'monitoring/notification-deliveries', redirect: '/platform-ops/alert-center/notification-history' },
  { path: 'monitoring/notifications', redirect: '/platform-ops/alert-center/notification-history' },
  {
    path: 'platform/email',
    name: 'PlatformOpsSettingsEmail',
    component: lazyRoute(() => import('./pages/platform/settings/EmailSettings.vue')),
  },
  {
    path: 'platform/authentication',
    name: 'PlatformOpsAuthentication',
    component: lazyRoute(() => import('./pages/platform/settings/IdentitySettings.vue')),
  },
  {
    path: 'platform/runtime-environment',
    name: 'PlatformOpsRuntimeEnvironment',
    component: lazyRoute(() => import('./pages/platform/settings/EnvironmentSettings.vue')),
  },
  {
    path: 'platform/integrations',
    name: 'PlatformOpsIntegrations',
    component: lazyRoute(() => import('./pages/platform/PlatformIntegrations.vue')),
  },
  { path: 'platform/settings/email', redirect: '/platform-ops/platform/email' },
  { path: 'platform/settings/turnstile', redirect: '/platform-ops/platform/authentication' },
  { path: 'platform/settings/google-oauth', redirect: '/platform-ops/platform/authentication' },
  { path: 'platform/settings/identity', redirect: '/platform-ops/platform/authentication' },
  { path: 'platform/settings/environment', redirect: '/platform-ops/platform/runtime-environment' },
  {
    path: 'platform/agent-releases',
    name: 'PlatformOpsAgentReleases',
    component: lazyRoute(() => import('./pages/platform/PlatformAgentReleases.vue')),
  },
  {
    path: 'platform/bootstrap-templates',
    redirect: '/platform-ops/platform/agent-releases',
  },
  {
    path: 'engine',
    component: () => import('./layout/PlatformEngineLayout.vue'),
    children: [
      { path: '', redirect: '/platform-ops/engine/ai-settings' },
      {
        path: 'ai-settings',
        component: lazyRoute(() => import('../pages/insight/InsightAiSettings.vue')),
      },
      {
        path: 'ai-settings/add',
        component: lazyRoute(() => import('../pages/insight/AiModelFormPage.vue')),
      },
      {
        path: 'ai-settings/:uuid/edit',
        component: lazyRoute(() => import('../pages/insight/AiModelFormPage.vue')),
      },
      {
        path: 'usage',
        component: lazyRoute(() => import('../pages/insight/InsightUsage.vue')),
      },
      {
        path: 'gateways',
        component: lazyRoute(() => import('../pages/insight/InsightDataGateways.vue')),
      },
      {
        path: 'data-connections',
        component: lazyRoute(() => import('./pages/engine/DataConnections.vue')),
      },
      {
        path: 'knowledge-base',
        component: lazyRoute(() => import('../pages/insight/InsightKnowledgeBase.vue')),
      },
      {
        path: 'knowledge-base/add',
        component: lazyRoute(() => import('../pages/insight/KnowledgeSourceFormPage.vue')),
      },
      {
        path: 'knowledge-base/:id/edit',
        component: lazyRoute(() => import('../pages/insight/KnowledgeSourceFormPage.vue')),
      },
      {
        path: 'assistants',
        component: lazyRoute(() => import('../pages/insight/InsightAssistants.vue')),
      },
      {
        path: 'assistants/add',
        component: lazyRoute(() => import('../pages/insight/AssistantFormPage.vue')),
      },
      {
        path: 'assistants/:uuid/edit',
        component: lazyRoute(() => import('../pages/insight/AssistantFormPage.vue')),
      },
      {
        path: 'skills',
        component: lazyRoute(() => import('../pages/insight/InsightSkills.vue')),
      },
      {
        path: 'skills/add',
        component: lazyRoute(() => import('../pages/insight/SkillFormPage.vue')),
      },
      {
        path: 'skills/:uuid/edit',
        component: lazyRoute(() => import('../pages/insight/SkillFormPage.vue')),
      },
      {
        path: 'mcp-servers',
        component: lazyRoute(() => import('../pages/insight/InsightMcpServers.vue')),
      },
      {
        path: 'mcp-servers/add',
        component: lazyRoute(() => import('../pages/insight/McpServerFormPage.vue')),
      },
      {
        path: 'mcp-servers/:uuid/edit',
        component: lazyRoute(() => import('../pages/insight/McpServerFormPage.vue')),
      },
    ],
  },
  {
    path: 'audit-center/audit-logs',
    name: 'PlatformOpsAuditLogs',
    component: lazyRoute(() => import('./pages/audit/PlatformAuditLogs.vue')),
  },
]
