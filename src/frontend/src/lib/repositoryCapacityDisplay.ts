export type RepositoryCapacityLike = {
  capacity_bytes?: number
  estimated_usage_bytes?: number
  config?: { quota_gb?: number | string | null } | null
}

export function repositoryEffectiveCapacityBytes(row: RepositoryCapacityLike): number {
  const stored = Number(row.capacity_bytes || 0)
  if (stored > 0) return stored
  const quotaGb = Number(row.config?.quota_gb ?? 0)
  if (quotaGb > 0) return Math.round(quotaGb * 1024 ** 3)
  return 0
}

export function repositoryCapacityParts(row: RepositoryCapacityLike): { used: number; total: number } {
  return {
    used: Math.max(0, Number(row.estimated_usage_bytes || 0)),
    total: repositoryEffectiveCapacityBytes(row),
  }
}

export function repositoryHasCapacityDisplay(row: RepositoryCapacityLike): boolean {
  const { used, total } = repositoryCapacityParts(row)
  return total > 0 || used > 0
}
