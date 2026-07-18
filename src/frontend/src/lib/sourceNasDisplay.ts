/** NAS mount source URI as used by mount(8): //host/share (CIFS) or host:/export (NFS). */

export type NasLikeResource = {
  resource_type?: string
  config?: Record<string, unknown>
  connection_summary?: string
  mount_point?: string
}

function configString(config: Record<string, unknown> | undefined, key: string): string {
  const value = config?.[key]
  return typeof value === 'string' ? value.trim() : ''
}

export function nasMountProtocol(row: NasLikeResource): 'smb' | 'nfs' | null {
  const resourceType = (row.resource_type || '').toLowerCase()
  const protocol = configString(row.config, 'protocol').toLowerCase()
  if (resourceType === 'cifs' || protocol === 'smb' || protocol === 'cifs') return 'smb'
  if (resourceType === 'nfs' || protocol === 'nfs') return 'nfs'
  if (configString(row.config, 'share')) return 'smb'
  if (configString(row.config, 'export_path')) return 'nfs'
  const summary = (row.connection_summary || '').trim()
  if (summary.startsWith('//') || summary.startsWith('\\\\')) return 'smb'
  if (summary.includes(' · ')) {
    const path = summary.split('·')[1]?.trim() || ''
    if (path.startsWith('/')) return 'nfs'
    if (path) return 'smb'
  }
  return null
}

function nfsExportPath(row: NasLikeResource): string {
  const exportPath = configString(row.config, 'export_path')
  if (exportPath) return exportPath
  if ((row.resource_type || '').toLowerCase() === 'nfs') {
    return configString(row.config, 'path')
  }
  return ''
}

function smbShare(row: NasLikeResource): string {
  return configString(row.config, 'share').replace(/^\/+|\/+$/g, '')
}

function serverFromSummary(summary: string): string {
  const trimmed = summary.trim()
  if (!trimmed) return ''
  if (trimmed.startsWith('//')) {
    const rest = trimmed.slice(2)
    const slash = rest.indexOf('/')
    return slash >= 0 ? rest.slice(0, slash) : rest
  }
  if (trimmed.includes(' · ')) return trimmed.split('·')[0]?.trim() || ''
  const colon = trimmed.indexOf(':')
  if (colon > 0 && !trimmed.startsWith('http')) return trimmed.slice(0, colon)
  return ''
}

function shareOrExportFromSummary(summary: string, protocol: 'smb' | 'nfs' | null): string {
  const trimmed = summary.trim()
  if (!trimmed) return ''
  if (trimmed.startsWith('//')) {
    const rest = trimmed.slice(2)
    const slash = rest.indexOf('/')
    return slash >= 0 ? rest.slice(slash + 1).replace(/^\/+|\/+$/g, '') : ''
  }
  if (trimmed.includes(' · ')) return trimmed.split('·')[1]?.trim() || ''
  if (protocol === 'nfs') {
    const colon = trimmed.indexOf(':')
    if (colon > 0) return trimmed.slice(colon + 1)
  }
  return ''
}

export function nasServerAddress(row: NasLikeResource): string {
  const server = configString(row.config, 'server')
  if (server) return server
  const fromSummary = serverFromSummary(row.connection_summary || '')
  return fromSummary || '—'
}

export function nasShareOrExport(row: NasLikeResource): string {
  const protocol = nasMountProtocol(row)
  if (protocol === 'smb') {
    const share = smbShare(row)
    if (share) return share
  }
  if (protocol === 'nfs') {
    const exportPath = nfsExportPath(row)
    if (exportPath) return exportPath
  }
  const fromSummary = shareOrExportFromSummary(row.connection_summary || '', protocol)
  return fromSummary || '—'
}

export function nasProxyMountPoint(row: NasLikeResource): string {
  const path = configString(row.config, 'path')
  if (path) return path
  const mountPoint = (row.mount_point || '').trim()
  return mountPoint || '—'
}

export function sourceExternalId(row: { id: number; resource_type?: string }): string {
  const type = (row.resource_type || 'nas').toLowerCase()
  const prefix = type === 'local' ? 'AGT' : 'NAS'
  const idPart = String(Math.abs(row.id)).padStart(5, '0')
  const suffix = String.fromCharCode(65 + (Math.abs(row.id) % 26))
  return `${prefix}-${idPart}-${suffix}`
}

export function nasMountSourceUri(row: NasLikeResource): string {
  const summary = (row.connection_summary || '').trim()
  const server = configString(row.config, 'server') || serverFromSummary(summary)
  const protocol = nasMountProtocol(row)

  if (protocol === 'smb') {
    const share = smbShare(row) || shareOrExportFromSummary(summary, protocol)
    if (server && share) return `//${server}/${share}`
    if (server) return `//${server}`
    return share || '—'
  }

  if (protocol === 'nfs') {
    const exportPath = nfsExportPath(row) || shareOrExportFromSummary(summary, protocol)
    if (server && exportPath) return `${server}:${exportPath}`
    if (server) return server
    return exportPath || '—'
  }

  if (summary.startsWith('//')) return summary
  if (summary.startsWith('\\\\')) {
    return `//${summary.slice(2).replace(/\\/g, '/')}`
  }
  if (summary.includes(':') && !summary.includes(' · ')) return summary
  if (summary.includes(' · ')) {
    const [host, remote] = summary.split('·').map((part) => part.trim())
    if (host && remote) {
      if (remote.startsWith('/')) return `${host}:${remote}`
      return `//${host}/${remote.replace(/^\/+|\/+$/g, '')}`
    }
  }
  return summary || '—'
}
