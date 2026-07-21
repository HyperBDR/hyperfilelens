import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const taskDetailSurfaces = [
  'pages/ops/Tasks.vue',
  'pages/protection/components/TaskDetailDrawer.vue',
  'pages/protection/components/FlowBackupSourceDetailDrawer.vue',
  'pages/protection/BackupDetail.vue',
  'pages/protection/components/BackupSourceHistorySection.vue',
]

describe('task detail drawer scroll reset coverage', () => {
  it.each(taskDetailSurfaces)('%s resets its main drawer body when opened', (relativePath) => {
    const source = readFileSync(resolve(process.cwd(), 'src', relativePath), 'utf8')

    expect(source).toContain('useDrawerScrollReset')
    expect(source).toContain('ref="drawerScrollAnchorRef"')
    expect(source).toContain('resetDrawerScroll()')
  })
})
