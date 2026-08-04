/** Shared NAS source create payload for Wizard / Protection / Backup Sources. */

export type NasSourceProtocol = 'smb' | 'nfs'

export type NasSourceCreateInput = {
  name: string
  protocol: NasSourceProtocol
  mountPath: string
  boundNodeId: number | null
  smb?: {
    server: string
    share: string
    username: string
    password: string
    domain?: string
    options?: string
  }
  nfs?: {
    server: string
    exportPath: string
    options?: string
  }
}

export function backupSelectableNasId(resourceId: number): string {
  return `nas:${resourceId}`
}

export function buildNasSourceCreatePayload(input: NasSourceCreateInput): Record<string, unknown> {
  const config: Record<string, string> = {
    protocol: input.protocol,
    path: input.mountPath.trim(),
  }
  const credentials: Record<string, string> = {}

  if (input.protocol === 'smb') {
    const smb = input.smb
    if (!smb) {
      throw new Error('SMB credentials are required for SMB NAS sources')
    }
    config.server = smb.server.trim()
    config.share = smb.share.trim()
    credentials.username = smb.username.trim()
    credentials.password = smb.password
    if (smb.domain?.trim()) credentials.domain = smb.domain.trim()
    if (smb.options?.trim()) config.options = smb.options.trim()
  } else {
    const nfs = input.nfs
    if (!nfs) {
      throw new Error('NFS connection details are required for NFS NAS sources')
    }
    config.server = nfs.server.trim()
    config.export_path = nfs.exportPath.trim()
    if (nfs.options?.trim()) config.options = nfs.options.trim()
  }

  return {
    name: input.name.trim(),
    description: '',
    resource_type: 'nas',
    config,
    credentials,
    bound_node_id: input.boundNodeId,
  }
}
