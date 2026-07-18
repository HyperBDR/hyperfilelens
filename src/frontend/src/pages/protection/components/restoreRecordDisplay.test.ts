import { describe, expect, it } from 'vitest'
import type { RestoreRecord, RestoreRecordItem } from '../../../lib/restoreApi'
import {
  restoreRecordPathMappings,
  restoreRecordSnapshotLabel,
  shouldShowRestoreRecordProgress,
} from './restoreRecordDisplay'

const item = {
  id: 11,
  source_path: '/data',
  selected_paths: [],
  target_path: '/restore/data',
  status: 'success',
} as RestoreRecordItem

function record(overrides: Partial<RestoreRecord> = {}): RestoreRecord {
  return {
    id: 1,
    source_snapshot_id: 81,
    source_snapshot_uid: 'snapshot-uid-81',
    items: [item],
    task_summary: {
      status: 'success',
      progress: 100,
      started_at: null,
      finished_at: null,
    },
    ...overrides,
  } as RestoreRecord
}

describe('restore record display', () => {
  it.each(['pending', 'success', 'failed', 'cancelled', 'timeout', ''])(
    'shows a status tag instead of progress for %s',
    (status) => {
      expect(shouldShowRestoreRecordProgress(record({
        task_summary: { status, progress: 0, started_at: null, finished_at: null },
      }))).toBe(false)
    },
  )

  it('shows progress only while the restore is running', () => {
    expect(shouldShowRestoreRecordProgress(record({
      task_summary: { status: 'RUNNING', progress: 42, started_at: null, finished_at: null },
    }))).toBe(true)
  })

  it('uses the snapshot UID and falls back to the internal ID', () => {
    expect(restoreRecordSnapshotLabel(record())).toBe('snapshot-uid-81')
    expect(restoreRecordSnapshotLabel(record({ source_snapshot_uid: '' }))).toBe('#81')
  })

  it('flattens selected paths into one-level mappings', () => {
    const rows = restoreRecordPathMappings(record({
      items: [{
        ...item,
        selected_paths: ['docs/report.pdf', 'images'],
      }],
    }))

    expect(rows.map((row) => ({ path: row.sourcePath, kind: row.sourceKind }))).toEqual([
      { path: '/data/docs/report.pdf', kind: 'file' },
      { path: '/data/images', kind: 'dir' },
    ])
  })

  it('keeps an item without selected paths as a single mapping', () => {
    expect(restoreRecordPathMappings(record())).toMatchObject([
      { sourcePath: '/data', sourceKind: 'dir', item: { id: 11 } },
    ])
  })
})
