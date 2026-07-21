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

describe('FlowBackupSourceDetailDrawer task columns', () => {
  it('removes Current Step and keeps the remaining columns within the full-size drawer', () => {
    const tasksTab = sourceBetween(
      '<el-tab-pane :label="t(\'protection.backupDetail.tabTasks\')" name="tasks">',
      '<ElDrawer\n    v-model="taskAdvancedFilterOpen"',
    )

    expect(tasksTab).not.toContain("t('protection.backupsPage.flowTaskColPhase')")
    expect(tasksTab).toContain('<el-table-column :label="t(\'ops.task.colName\')" width="275" fixed>')
    expect(tasksTab).toContain('<el-table-column :label="t(\'protection.backupDetail.colTaskType\')" width="205">')
    expect(tasksTab).toContain('<el-table-column :label="t(\'protection.backupDetail.colTaskStatus\')" width="115">')
    expect(tasksTab).toContain('<el-table-column :label="t(\'protection.backupsPage.flowTaskColProgress\')" min-width="165">')
    expect(tasksTab).toContain('<el-table-column :label="t(\'ops.task.colTrigger\')" width="105">')
    expect(tasksTab).toContain('<el-table-column :label="t(\'protection.backupDetail.colCreated\')" min-width="160">')

    expect(275 + 205 + 115 + 165 + 105 + 160).toBeLessThanOrEqual(1040)
  })
})

describe('FlowBackupSourceDetailDrawer snapshot expansion state', () => {
  it('allocates enough width for both snapshot timestamps', () => {
    const snapshotTab = sourceBetween(
      '<el-tab-pane :label="t(\'protection.backupsPage.flowSourceDetailTabSnapshots\')" name="snapshots">',
      '<el-tab-pane :label="t(\'protection.backupsPage.flowSourceDetailTabRestoreRecords\')" name="restoreRecords">',
    )

    expect(snapshotTab).toContain('<el-table-column :label="t(\'protection.backupDetail.colSnapId\')" width="140" fixed>')
    expect(snapshotTab).toContain('<el-table-column :label="t(\'protection.backupDetail.colSnapStart\')" width="160">')
    expect(snapshotTab).toContain('<el-table-column :label="t(\'protection.backupDetail.colSnapEnd\')" width="160">')
  })

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
