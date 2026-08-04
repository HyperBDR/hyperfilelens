import { describe, expect, it } from 'vitest'

import { backupSelectableNasId, buildNasSourceCreatePayload } from './nasSourceCreate'

describe('buildNasSourceCreatePayload', () => {
  it('builds an SMB create payload with optional domain and mount options', () => {
    expect(
      buildNasSourceCreatePayload({
        name: 'SMB_192.168.10.33_source',
        protocol: 'smb',
        mountPath: '/var/lib/hyperfilelens-agent/mounts/custom/smb-192.168.10.33-source',
        boundNodeId: 12,
        smb: {
          server: '192.168.10.33',
          share: 'source',
          username: 'backup',
          password: 'secret',
          domain: 'CORP',
          options: 'vers=3.0',
        },
      }),
    ).toEqual({
      name: 'SMB_192.168.10.33_source',
      description: '',
      resource_type: 'nas',
      config: {
        protocol: 'smb',
        path: '/var/lib/hyperfilelens-agent/mounts/custom/smb-192.168.10.33-source',
        server: '192.168.10.33',
        share: 'source',
        options: 'vers=3.0',
      },
      credentials: {
        username: 'backup',
        password: 'secret',
        domain: 'CORP',
      },
      bound_node_id: 12,
    })
  })

  it('builds an NFS create payload with export path', () => {
    expect(
      buildNasSourceCreatePayload({
        name: 'NFS_192.168.10.35_data',
        protocol: 'nfs',
        mountPath: '/var/lib/hyperfilelens-agent/mounts/custom/nfs-192.168.10.35-data',
        boundNodeId: 33,
        nfs: {
          server: '192.168.10.35',
          exportPath: '/',
          options: 'nfsvers=3,proto=tcp,nolock,rw',
        },
      }),
    ).toEqual({
      name: 'NFS_192.168.10.35_data',
      description: '',
      resource_type: 'nas',
      config: {
        protocol: 'nfs',
        path: '/var/lib/hyperfilelens-agent/mounts/custom/nfs-192.168.10.35-data',
        server: '192.168.10.35',
        export_path: '/',
        options: 'nfsvers=3,proto=tcp,nolock,rw',
      },
      credentials: {},
      bound_node_id: 33,
    })
  })

  it('formats backup-selectable NAS ids', () => {
    expect(backupSelectableNasId(42)).toBe('nas:42')
  })
})
