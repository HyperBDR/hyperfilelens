import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const drawer = readFileSync(resolve(process.cwd(), 'src/pages/protection/components/FlowBackupSourceDetailDrawer.vue'), 'utf8')

function sourceBetween(start: string, end: string) {
  const startIndex = drawer.indexOf(start)
  const endIndex = drawer.indexOf(end, startIndex)
  expect(startIndex).toBeGreaterThanOrEqual(0)
  expect(endIndex).toBeGreaterThan(startIndex)
  return drawer.slice(startIndex, endIndex)
}

describe('FlowBackupSourceDetailDrawer snapshot expansion state', () => {
  it('preserves loaded snapshot details when the active tab refreshes its list', () => {
    const loader = sourceBetween(
      'async function loadSnapshotsForSource()',
      'async function downloadSelectedBrowserPaths()',
    )

    expect(loader).not.toContain('snapshotDetails.value = new Map()')
    expect(loader).not.toContain('expandedSnapshotRowKeys.value = []')
    expect(loader).not.toContain('selectedSnapshotId.value = null')
  })

  it('clears cached expansion state when pagination changes', () => {
    const paginationWatcher = sourceBetween(
      '() => [snapshotPagination.page, snapshotPagination.pageSize] as const,',
      'watch(sourceId,',
    )

    expect(paginationWatcher).toContain('selectedSnapshotId.value = null')
    expect(paginationWatcher).toContain('expandedSnapshotRowKeys.value = []')
    expect(paginationWatcher).toContain('snapshotDetails.value = new Map()')
  })
})
