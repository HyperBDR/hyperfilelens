import { lazyRoute } from '../router/lazyRoute'

/**
 * Community / OSS Platform Ops routes — AI Models (+ Runtime) shell.
 * Email / identity / environment page components stay here so the platform
 * extension can merge them into the full ops console. Data Gateways live in EE.
 */
export const platformOpsRoutes = [
  { path: '', redirect: '/platform-ops/engine/ai-settings' },
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
  { path: 'platform/settings/email', redirect: '/platform-ops/platform/email' },
  { path: 'platform/settings/turnstile', redirect: '/platform-ops/platform/authentication' },
  { path: 'platform/settings/google-oauth', redirect: '/platform-ops/platform/authentication' },
  { path: 'platform/settings/identity', redirect: '/platform-ops/platform/authentication' },
  { path: 'platform/settings/environment', redirect: '/platform-ops/platform/runtime-environment' },
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
      // Community bookmarks for the removed gateways menu → AI Models.
      { path: 'gateways', redirect: '/platform-ops/engine/ai-settings' },
      { path: 'gateways/add', redirect: '/platform-ops/engine/ai-settings' },
    ],
  },
]
