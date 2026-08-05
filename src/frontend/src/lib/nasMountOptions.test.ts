import { describe, expect, it } from 'vitest'
import { defaultNasMountOptions, SMB_DEFAULT_MOUNT_OPTIONS } from './nasMountOptions'

describe('NAS mount option defaults', () => {
  it('uses explicit UTF-8 SMB defaults without pinning the SMB protocol version', () => {
    expect(SMB_DEFAULT_MOUNT_OPTIONS).toBe('rw,iocharset=utf8')
    expect(SMB_DEFAULT_MOUNT_OPTIONS).not.toContain('vers=')
    expect(defaultNasMountOptions('smb')).toBe(SMB_DEFAULT_MOUNT_OPTIONS)
  })

  it('does not invent NFS mount defaults', () => {
    expect(defaultNasMountOptions('nfs')).toBe('')
  })
})
