export type NasMountProtocol = 'smb' | 'nfs'

// Keep the user-visible SMB default aligned with the Agent's filename contract.
export const SMB_DEFAULT_MOUNT_OPTIONS = 'rw,iocharset=utf8'

export function defaultNasMountOptions(protocol: NasMountProtocol): string {
  return protocol === 'smb' ? SMB_DEFAULT_MOUNT_OPTIONS : ''
}
