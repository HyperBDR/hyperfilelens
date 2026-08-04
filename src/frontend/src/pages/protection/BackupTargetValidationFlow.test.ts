import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const wizard = readFileSync(
  resolve(process.cwd(), 'src/pages/protection/BackupCreateWizard.vue'),
  'utf8',
)
const shell = readFileSync(
  resolve(process.cwd(), 'src/pages/protection/BackupConfigCreateWizard.vue'),
  'utf8',
)

describe('backup Target connection validation flow', () => {
  it('awaits validation before advancing from the Target step', () => {
    expect(wizard).toContain("if (createStep.value === 2 && !await validateCurrentBackupTargets()) return")
    expect(wizard).toContain('validateProtectionBackupTargets({')
    expect(wizard).toContain('if (targetValidationInProgress.value || isCreateStepLocked(createStep.value)) return')
  })

  it('shows row-level failures and invalidates stale results after assignment changes', () => {
    expect(wizard).toContain("classes.push('target-group-row--connection-failed')")
    expect(wizard).toContain('targetConnectionResult(group.key)?.message')
    expect(wizard).toContain('clearTargetConnectionResults()')
    expect(wizard).toContain("row?.scrollIntoView({ behavior: 'smooth'")
  })

  it('locks navigation behind a visible bounded loading state', () => {
    expect(wizard).toContain(':busy="targetValidationInProgress"')
    expect(wizard).toContain('const TARGET_VALIDATION_CLIENT_TIMEOUT_MS = 125_000')
    expect(wizard).toContain("t('protection.backupsPage.targetValidationTimedOut')")
    expect(wizard).toContain('if (targetValidationController === controller) {')
    expect(shell).toContain('v-loading="busy"')
    expect(shell).toContain(':disabled="bootstrapping || busy"')
  })
})
