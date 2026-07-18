import { describe, expect, it } from 'vitest'
import { isSnapshotDirectoryBrowsable } from './snapshotBrowseEligibility'

const availableDirectory = {
  status: 'available',
  kopia_snapshot_id: 'kopia-snapshot-1',
}

describe('isSnapshotDirectoryBrowsable', () => {
  it.each(['available', 'AVAILABLE', 'partial', 'PARTIAL'])(
    'allows browsing for a %s parent snapshot',
    (snapshotStatus) => {
      expect(isSnapshotDirectoryBrowsable(snapshotStatus, availableDirectory)).toBe(true)
    },
  )

  it.each([undefined, '', 'creating', 'failed', 'deleting', 'deleted', 'delete_failed'])(
    'blocks browsing for a %s parent snapshot',
    (snapshotStatus) => {
      expect(isSnapshotDirectoryBrowsable(snapshotStatus, availableDirectory)).toBe(false)
    },
  )

  it('blocks browsing when the directory snapshot is unavailable', () => {
    expect(isSnapshotDirectoryBrowsable('available', {
      ...availableDirectory,
      status: 'failed',
    })).toBe(false)
  })

  it.each([undefined, null, ''])(
    'blocks browsing when the directory Kopia snapshot ID is %s',
    (kopiaSnapshotId) => {
      expect(isSnapshotDirectoryBrowsable('available', {
        ...availableDirectory,
        kopia_snapshot_id: kopiaSnapshotId,
      })).toBe(false)
    },
  )
})
