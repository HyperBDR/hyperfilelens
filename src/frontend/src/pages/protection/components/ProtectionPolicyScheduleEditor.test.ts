import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const editorSource = readFileSync(
  resolve(process.cwd(), 'src/pages/protection/components/ProtectionPolicyEditorForm.vue'),
  'utf8',
)
const wizardSource = readFileSync(
  resolve(process.cwd(), 'src/pages/protection/BackupCreateWizard.vue'),
  'utf8',
)

describe('protection policy quick schedule editor', () => {
  it('exposes timezone, activation, cycle, weekly, monthly, and exact-time controls', () => {
    expect(editorSource).toContain('v-model="policyForm.scheduleTimezone"')
    expect(editorSource).toContain('v-model="policyForm.scheduleStartsAt"')
    expect(editorSource).toContain('v-model="policyForm.quickScheduleType"')
    expect(editorSource).toContain('v-model="policyForm.scheduleWeekdays"')
    expect(editorSource).toContain('policyForm.scheduleMonthDays.includes(day)')
    expect(editorSource).toContain('v-model="policyForm.scheduleTime"')
    expect(editorSource).toContain("policyForm.scheduleMonthEnd = !policyForm.scheduleMonthEnd")
  })

  it('uses the shared policy payload mapper in the backup wizard', () => {
    expect(wizardSource).toContain('policyFormToWritePayload(snapshot)')
    expect(wizardSource).not.toContain('function policyFormToPayload(')
    expect(wizardSource).not.toContain('`*/${Math.max(1, Number(form.simpleIntervalValue)')
  })
})
