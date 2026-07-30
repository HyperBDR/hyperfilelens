import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const taskDetailSurfaces = [
  'pages/node/Repositories.vue',
  'pages/ops/Tasks.vue',
  'pages/protection/BackupDetail.vue',
  'pages/protection/DataProtection.vue',
  'pages/protection/components/BackupSourceHistorySection.vue',
  'pages/protection/components/FlowBackupSourceDetailDrawer.vue',
  'pages/protection/components/TaskDetailDrawer.vue',
  'platform-ops/pages/monitoring/MonitoringTasks.vue',
]

const tabbedTaskDetailSurfaces = [
  'pages/ops/Tasks.vue',
  'pages/protection/components/FlowBackupSourceDetailDrawer.vue',
  'pages/protection/components/TaskDetailDrawer.vue',
]

function frontendSource(relativePath: string) {
  return readFileSync(resolve(process.cwd(), 'src', relativePath), 'utf8')
}

describe('task detail payload visibility', () => {
  it.each(taskDetailSurfaces)('%s does not expose an Input / Output tab', (relativePath) => {
    const source = frontendSource(relativePath)

    expect(source).not.toContain('name="payload"')
    expect(source).not.toContain("t('ops.task.payloads')")
    expect(source).not.toContain("t('protection.backupsPage.flowSourceDetailPayloads')")
  })

  it.each(tabbedTaskDetailSurfaces)('%s preserves the interpreted task tabs', (relativePath) => {
    const source = frontendSource(relativePath)

    expect(source).toContain('name="steps"')
    expect(source).toContain('name="resources"')
  })

  it('removes the hidden task payload labels from source locales', () => {
    const genericLocale = frontendSource('locales/en.ts')
    const protectionLocale = frontendSource('locales/enProtectionPages.ts')

    expect(genericLocale).not.toContain("payloads: 'Input / Output'")
    expect(genericLocale).not.toContain("requestPayload: 'Request Payload'")
    expect(genericLocale).not.toContain("resultPayload: 'Result Payload'")
    expect(protectionLocale).not.toContain("flowSourceDetailPayloads: 'Input / Output'")
  })
})
