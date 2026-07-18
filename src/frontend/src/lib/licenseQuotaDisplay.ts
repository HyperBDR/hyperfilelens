import type { LicenseUsage } from './subscriptionApi'

export type QuotaUsageRow = {
  key: string
  labelKey: string
  used: number
  limit: number
  suffix?: string
}

type QuotaDisplayDef = {
  key: string
  labelKey: string
  usageKey: string
  limitKey: string
  suffix?: string
}

/** Shared quota metrics for subscription billing and dashboard overview. */
export const SUBSCRIPTION_QUOTA_DEFS: QuotaDisplayDef[] = [
  {
    key: 'agents',
    labelKey: 'licenseQuota.sourceHosts',
    usageKey: 'agents_count',
    limitKey: 'max_source_hosts',
  },
  {
    key: 'sourceNas',
    labelKey: 'licenseQuota.sourceNas',
    usageKey: 'source_nas_count',
    limitKey: 'max_source_nas',
  },
  {
    key: 'proxies',
    labelKey: 'licenseQuota.sourceAgents',
    usageKey: 'proxies_count',
    limitKey: 'max_source_proxies',
  },
  {
    key: 'objectStorage',
    labelKey: 'licenseQuota.objectStorage',
    usageKey: 'object_storage_count',
    limitKey: 'max_object_storage',
  },
  {
    key: 'targetNas',
    labelKey: 'licenseQuota.targetNas',
    usageKey: 'target_nas_count',
    limitKey: 'max_target_nas',
  },
  {
    key: 'standaloneDisk',
    labelKey: 'licenseQuota.standaloneDisk',
    usageKey: 'standalone_disk_count',
    limitKey: 'max_standalone_disk',
  },
]

export const SUBSCRIPTION_QUOTA_FALLBACK_LIMITS: Record<string, number> = {
  max_source_hosts: 100,
  max_source_nas: 100,
  max_source_proxies: 100,
  max_object_storage: 100,
  max_target_nas: 100,
  max_standalone_disk: 100,
}

export function quotaDefsForDashboard(): QuotaDisplayDef[] {
  return SUBSCRIPTION_QUOTA_DEFS
}

export function quotaDefsForSubscription(): QuotaDisplayDef[] {
  return SUBSCRIPTION_QUOTA_DEFS
}

export function buildQuotaRows(
  usage: LicenseUsage,
  limits: Record<string, number>,
  license?: Record<string, unknown>,
  options?: { subscription?: boolean },
): QuotaUsageRow[] {
  const defs = options?.subscription ? quotaDefsForSubscription() : quotaDefsForDashboard()
  const mergedLimits = { ...SUBSCRIPTION_QUOTA_FALLBACK_LIMITS, ...limits }
  if (license) {
    for (const { limitKey } of SUBSCRIPTION_QUOTA_DEFS) {
      if (license[limitKey] !== undefined) mergedLimits[limitKey] = Number(license[limitKey])
    }
  }

  return defs.map(({ key, labelKey, usageKey, limitKey, suffix }) => ({
    key,
    labelKey,
    used: Number(usage[usageKey]) || 0,
    limit: Number(mergedLimits[limitKey]) || 0,
    suffix,
  }))
}

export function quotaUsagePercent(used: number, limit: number): number {
  if (limit < 0) return 0
  if (!limit) return 0
  return Math.min(100, Math.round((used / limit) * 100))
}
