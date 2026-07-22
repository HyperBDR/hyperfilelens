import { describe, expect, it } from 'vitest'
import {
  isBackupTargetCompatible,
  requiresCrossProxyRepositoryServerHost,
} from './backupTargetCompatibility'

describe('isBackupTargetCompatible', () => {
  it('allows a proxy-bound repository on the same proxy without server mode', () => {
    expect(isBackupTargetCompatible(
      { sourceType: 'nas', boundNodeId: 4 },
      { repoType: 'NAS', bindNodeType: 'proxy', bindNodeId: 4, crossProxyReady: false },
    )).toBe(true)
  })

  it('requires an explicit host only when a NAS source uses another proxy', () => {
    expect(requiresCrossProxyRepositoryServerHost([
      { sourceType: 'nas', boundNodeId: 4 },
      { sourceType: 'host', boundNodeId: 8 },
    ], 4)).toBe(false)
    expect(requiresCrossProxyRepositoryServerHost([
      { sourceType: 'nas', boundNodeId: 4 },
      { sourceType: 'nas', boundNodeId: 7 },
    ], 4)).toBe(true)
  })

  it('allows a different proxy only when repository server access is ready', () => {
    const source = { sourceType: 'nas' as const, boundNodeId: 4 }
    expect(isBackupTargetCompatible(source, {
      repoType: 'NAS', bindNodeType: 'proxy', bindNodeId: 1, crossProxyReady: true,
    })).toBe(true)
    expect(isBackupTargetCompatible(source, {
      repoType: 'PROXY_FS', bindNodeType: 'proxy', bindNodeId: 1, crossProxyReady: false,
    })).toBe(false)
  })

  it('does not restrict agent or unbound repositories', () => {
    expect(isBackupTargetCompatible(
      { sourceType: 'host', boundNodeId: null },
      { repoType: 'NAS', bindNodeType: 'proxy', bindNodeId: 1, crossProxyReady: false },
    )).toBe(true)
    expect(isBackupTargetCompatible(
      { sourceType: 'nas', boundNodeId: 4 },
      { repoType: 'NAS', bindNodeType: null, bindNodeId: null },
    )).toBe(true)
  })
})
