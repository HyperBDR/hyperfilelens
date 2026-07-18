import type { StorageRepository } from './storageRepositoryApi'

function configString(config: Record<string, unknown> | undefined, key: string): string {
  const value = config?.[key]
  return typeof value === 'string' ? value.trim() : ''
}

function normalizeLocationPath(path?: string) {
  return (path || '').trim().replace(/^\/+|\/+$/g, '')
}

function ensureAbsolutePath(path?: string) {
  const normalized = normalizeLocationPath(path)
  return normalized ? `/${normalized}` : ''
}

/** Primary location line — aligned with storage repository list (s3://bucket, NAS path, etc.). */
export function storageRepositoryLocation(repo: StorageRepository): string {
  const config = repo.config ?? {}
  const repoType = String(repo.repo_type || '').toLowerCase()

  if (repoType === 's3') {
    const bucket = (repo.s3_bucket || configString(config, 'bucket') || repo.name || '').trim()
    const endpoint = configString(config, 'endpoint')
    const prefix = configString(config, 'prefix')
    if (!bucket) return ''
    const base = endpoint ? `s3://${bucket}@${endpoint}` : `s3://${bucket}`
    const normalizedPrefix = normalizeLocationPath(prefix)
    return normalizedPrefix ? `${base}/${normalizedPrefix}` : base
  }

  if (repoType === 'proxy_fs') {
    const proxyIp = String(repo.bind_node_ip || '').trim()
    const repositoryPath = configString(config, 'proxy_node_dir') || configString(config, 'mount_path')
    if (!proxyIp) return repositoryPath
    return repositoryPath ? `local://${proxyIp}${ensureAbsolutePath(repositoryPath)}` : `local://${proxyIp}`
  }

  const serverAddress = configString(config, 'server_address') || configString(config, 'nfs_host')
  const sharePath = configString(config, 'share_path') || configString(config, 'nfs_export')
  const protocol = String(repo.nas_protocol || config.protocol || '').toLowerCase()

  if (serverAddress && sharePath) return `${protocol === 'smb' ? 'smb' : 'nfs'}://${serverAddress.replace(/^\/+|\/+$/g, '')}/${normalizeLocationPath(sharePath)}`
  if (serverAddress) return `${protocol === 'smb' ? 'smb' : 'nfs'}://${serverAddress.replace(/^\/+|\/+$/g, '')}`

  return ''
}
