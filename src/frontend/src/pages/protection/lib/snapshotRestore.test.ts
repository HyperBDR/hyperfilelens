import { describe, expect, it } from 'vitest'
import type { BackupSourceSnapshot } from '../../../lib/protectionBackupConfigApi'
import { isSnapshotRestorable } from './snapshotRestore'

function snapshot(overrides: Partial<BackupSourceSnapshot> = {}): BackupSourceSnapshot {
  return {
    id: 42,
    snapshot_uid: 'snap-42',
    source_type: 'agent',
    source_ref_id: 7,
    source_display_name: 'host-7',
    backup_config_id: 9,
    backup_config_name: 'backup-9',
    repository_id: 3,
    repository_display_name: 'repo-3',
    task_id: 11,
    task_uuid: 'task-11',
    trigger_type: 'manual',
    status: 'available',
    created_at: '2026-07-16T00:00:00Z',
    directory_count: 1,
    successful_directory_count: 1,
    failed_directory_count: 0,
    kopia_snapshot_count: 1,
    total_size_bytes: 1024,
    file_count: 2,
    dir_count: 1,
    ...overrides,
  }
}

describe('snapshot restore entry', () => {
  it('accepts available and partial snapshots with a usable directory snapshot', () => {
    expect(isSnapshotRestorable(snapshot())).toBe(true)
    expect(isSnapshotRestorable(snapshot({ status: 'partial' }))).toBe(true)
  })

  it('rejects failed snapshots and snapshots without usable physical directories', () => {
    expect(isSnapshotRestorable(snapshot({ status: 'failed' }))).toBe(false)
    expect(isSnapshotRestorable(snapshot({ successful_directory_count: 0 }))).toBe(false)
    expect(isSnapshotRestorable(snapshot({ kopia_snapshot_count: 0 }))).toBe(false)
  })
})
