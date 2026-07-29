import type { RouteRecordRaw } from 'vue-router'

export const PROTECTION_RETENTION_LEGACY_ROUTE = {
  path: 'protection/retention',
  redirect: '/protection/policies?tab=backup',
} satisfies RouteRecordRaw
