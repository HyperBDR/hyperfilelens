export type BackupTargetCompatibilitySource = {
  sourceType: 'host' | 'nas'
  boundNodeId?: number | string | null
}

export type BackupTargetCompatibilityRepository = {
  repoType: string
  bindNodeType?: string | null
  bindNodeId?: number | string | null
  crossProxyReady?: boolean
}

export function isBackupTargetCompatible(
  source: BackupTargetCompatibilitySource,
  repository: BackupTargetCompatibilityRepository,
) {
  if (source.sourceType !== 'nas') return true
  if (repository.repoType !== 'NAS' && repository.repoType !== 'PROXY_FS') return true
  if (repository.bindNodeType !== 'proxy' || !repository.bindNodeId) return true
  if (!source.boundNodeId) return false
  if (Number(source.boundNodeId) === Number(repository.bindNodeId)) return true
  return repository.crossProxyReady === true
}

export function requiresCrossProxyRepositoryServerHost(
  sources: BackupTargetCompatibilitySource[],
  repositoryBindNodeId?: number | string | null,
) {
  if (!repositoryBindNodeId) return false
  return sources.some((source) => (
    source.sourceType === 'nas'
    && (!source.boundNodeId || Number(source.boundNodeId) !== Number(repositoryBindNodeId))
  ))
}
