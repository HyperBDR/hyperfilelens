import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const page = readFileSync(resolve(process.cwd(), 'src/pages/protection/DataProtection.vue'), 'utf8')
const protectionLocale = readFileSync(resolve(process.cwd(), 'src/locales/enProtectionPages.ts'), 'utf8')

function sourceBetween(startMarker: string, endMarker: string) {
  const start = page.indexOf(startMarker)
  const end = page.indexOf(endMarker, start + 1)

  expect(start).toBeGreaterThan(-1)
  expect(end).toBeGreaterThan(start)
  return page.slice(start, end)
}

describe('create restore task missing-plan configure link', () => {
  it('exposes Configure Restore Plan inside the missing-plan warning cell', () => {
    const missingCell = sourceBetween(
      'class="recovery-plan-missing-cell"',
      ':label="t(\'protection.backupsPage.descSnapshot\')"',
    )

    expect(missingCell).toContain('recoveryPlanMissingTitle')
    expect(missingCell).toContain('recoveryPlanMissingDesc')
    expect(missingCell).toContain('recovery-plan-missing-cell__action')
    expect(missingCell).toContain('@click="openConfigureRestorePlanFromMissingRow(row)"')
    expect(missingCell).toContain('flowActionConfigureRecoveryPlan')
    expect(protectionLocale).toContain("flowActionConfigureRecoveryPlan: 'Configure Restore Plan'")
  })

  it('closes the restore chooser then opens the existing restore-plan editor', () => {
    const handler = sourceBetween(
      'async function openConfigureRestorePlanFromMissingRow',
      'function taskPayload(task: TaskRow)',
    )

    expect(handler).toContain('await closeRecoveryWizard()')
    expect(handler).toContain('openBackupConfigEdit([config], \'recovery\')')
    expect(handler).toContain('getBackupConfig(configId)')
  })
})
