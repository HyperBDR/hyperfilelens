import { describe, expect, it } from 'vitest'

import { buildGeneratedNasMountDir, customMountPath, DEFAULT_AGENT_DATA_DIR } from './nasMountPath'

describe('nasMountPath', () => {
  it('builds canonical custom mount dir under agent data root', () => {
    expect(
      buildGeneratedNasMountDir({
        protocol: 'smb',
        smbServer: '192.168.1.10',
        smbShare: '/media',
      }),
    ).toBe(`${DEFAULT_AGENT_DATA_DIR}/mounts/custom/smb-192.168.1.10-media`)
  })

  it('builds explicit custom mount paths', () => {
    expect(customMountPath('nas-data')).toBe(
      `${DEFAULT_AGENT_DATA_DIR}/mounts/custom/nas-data`,
    )
  })
})
