import type { BackupSourceSnapshot } from '../../../lib/protectionBackupConfigApi'

export function isSnapshotRestorable(snapshot: BackupSourceSnapshot) {
  const status = String(snapshot.status || '').toLowerCase()
  return (status === 'available' || status === 'partial')
    && Number(snapshot.successful_directory_count || 0) > 0
    && Number(snapshot.kopia_snapshot_count || 0) > 0
}
