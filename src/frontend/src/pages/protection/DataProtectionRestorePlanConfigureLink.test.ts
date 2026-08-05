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
  it('renders missing plans with the shared recovery-plan cell style and configure action', () => {
    const missingCell = sourceBetween(
      'create-recovery-plan-cell--pending recovery-plan-missing-cell',
      ':label="t(\'protection.backupsPage.descSnapshot\')"',
    )

    expect(missingCell).toContain('create-recovery-plan-cell__status')
    expect(missingCell).toContain('create-recovery-plan-cell__dot')
    expect(missingCell).toContain('create-recovery-plan-cell__meta')
    expect(missingCell).toContain('recoveryPlanMissingTitle')
    expect(missingCell).toContain('recoveryPlanMissingDesc')
    expect(missingCell).toContain('recovery-plan-missing-cell__action')
    expect(missingCell).toContain('@click="openConfigureRestorePlanFromMissingRow(row)"')
    expect(missingCell).toContain('flowActionConfigureRecoveryPlan')
    expect(missingCell).toContain('<Route')
    expect(missingCell).not.toContain('AlertTriangle')
    expect(protectionLocale).toContain("flowActionConfigureRecoveryPlan: 'Configure Restore Plan'")
    expect(page).toContain('.recovery-plan-missing-cell .create-recovery-plan-cell__meta')
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
