import { lazyRoute } from '../router/lazyRoute'

export const platformOpsRoutes = [
  { path: '', redirect: '/platform-ops/monitoring/host' },
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
    path: 'monitoring/host',
    name: 'PlatformOpsMonitoringHost',
    component: lazyRoute(() => import('./pages/monitoring/MonitoringHost.vue')),
  },
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
    path: 'platform/settings/email',
    name: 'PlatformOpsSettingsEmail',
    component: lazyRoute(() => import('./pages/platform/settings/EmailSettings.vue')),
  },
  {
    path: 'platform/settings/turnstile',
    name: 'PlatformOpsSettingsTurnstile',
    component: lazyRoute(() => import('./pages/platform/settings/TurnstileSettings.vue')),
  },
  {
    path: 'platform/settings/google-oauth',
    name: 'PlatformOpsSettingsGoogleOAuth',
    component: lazyRoute(() => import('./pages/platform/settings/GoogleOAuthSettings.vue')),
  },
  {
    path: 'platform/settings/identity',
    name: 'PlatformOpsSettingsIdentity',
    component: lazyRoute(() => import('./pages/platform/settings/IdentitySettings.vue')),
  },
  {
    path: 'platform/settings/environment',
    name: 'PlatformOpsSettingsEnvironment',
    component: lazyRoute(() => import('./pages/platform/settings/EnvironmentSettings.vue')),
  },
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
        path: 'gateways',
        component: lazyRoute(() => import('../pages/insight/InsightDataGateways.vue')),
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
]
