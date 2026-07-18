import { describe, expect, it } from 'vitest'

import { customMountPath } from './nasMountPath'
import {
  nasMountProtocol,
  nasMountSourceUri,
  nasProxyMountPoint,
  nasServerAddress,
  nasShareOrExport,
} from './sourceNasDisplay'

describe('nasMountSourceUri', () => {
  it('formats SMB mount source as //host/share', () => {
    expect(
      nasMountSourceUri({
        resource_type: 'nas',
        config: {
          protocol: 'smb',
          server: '192.168.14.23',
          share: 'backup',
        },
      }),
    ).toBe('//192.168.14.23/backup')
  })

  it('formats NFS mount source as host:/export', () => {
    expect(
      nasMountSourceUri({
        resource_type: 'nas',
        config: {
          protocol: 'nfs',
          server: '192.168.14.23',
          export_path: '/srv/nfs/backup',
          path: customMountPath('192.168.14.23-srv-nfs-backup'),
        },
      }),
    ).toBe('192.168.14.23:/srv/nfs/backup')
  })

  it('converts dot-separated summary', () => {
    expect(
      nasMountSourceUri({
        resource_type: 'nas',
        config: {},
        connection_summary: '192.168.14.23 · backup',
      }),
    ).toBe('//192.168.14.23/backup')
    expect(
      nasMountSourceUri({
        resource_type: 'nas',
        config: {},
        connection_summary: '192.168.14.23 · /srv/nfs/backup',
      }),
    ).toBe('192.168.14.23:/srv/nfs/backup')
  })

  it('detects protocol from config fields', () => {
    expect(nasMountProtocol({ resource_type: 'nas', config: { share: 'data' } })).toBe('smb')
    expect(nasMountProtocol({ resource_type: 'nas', config: { export_path: '/export' } })).toBe('nfs')
  })
})

describe('nas list column helpers', () => {
  it('extracts server, share/export, and proxy mount point from config', () => {
    const smbMount = customMountPath('192.168.14.23-backup')
    expect(
      nasServerAddress({
        resource_type: 'nas',
        config: { protocol: 'smb', server: '192.168.14.23', share: 'backup', path: smbMount },
      }),
    ).toBe('192.168.14.23')
    expect(
      nasShareOrExport({
        resource_type: 'nas',
        config: { protocol: 'smb', server: '192.168.14.23', share: 'backup' },
      }),
    ).toBe('backup')
    expect(
      nasShareOrExport({
        resource_type: 'nas',
        config: {
          protocol: 'nfs',
          server: '192.168.31.88',
          export_path: '/srv/nfs/share',
          path: customMountPath('192.168.31.88-srv-nfs-share'),
        },
      }),
    ).toBe('/srv/nfs/share')
    expect(
      nasProxyMountPoint({
        resource_type: 'nas',
        mount_point: smbMount,
        config: { path: customMountPath('other') },
      }),
    ).toBe(customMountPath('other'))
    expect(
      nasProxyMountPoint({
        resource_type: 'nas',
        mount_point: smbMount,
        config: {},
      }),
    ).toBe(smbMount)
  })
})
