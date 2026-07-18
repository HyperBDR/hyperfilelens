import type { BackupSourceSnapshotDirectory } from '../../../lib/protectionBackupConfigApi'

type SnapshotDirectoryBrowseCandidate = Pick<BackupSourceSnapshotDirectory, 'status' | 'kopia_snapshot_id'>

export function isSnapshotDirectoryBrowsable(
  snapshotStatus: string | null | undefined,
  directory: SnapshotDirectoryBrowseCandidate,
) {
  const normalizedSnapshotStatus = String(snapshotStatus || '').toLowerCase()
  return (normalizedSnapshotStatus === 'available' || normalizedSnapshotStatus === 'partial')
    && directory.status === 'available'
    && Boolean(directory.kopia_snapshot_id)
}
