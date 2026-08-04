import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'


const page = readFileSync(resolve(process.cwd(), 'src/pages/protection/DataProtection.vue'), 'utf8')
const locale = readFileSync(resolve(process.cwd(), 'src/locales/enProtectionPages.ts'), 'utf8')

function sourceBetween(startMarker: string, endMarker: string) {
  const start = page.indexOf(startMarker)
  const end = page.indexOf(endMarker, start + startMarker.length)
  expect(start).toBeGreaterThan(-1)
  expect(end).toBeGreaterThan(start)
  return page.slice(start, end)
}

describe('Backup Wizard Step 3 server filters', () => {
  it('sends selected-field search and every quick/advanced filter to the server', () => {
    const load = sourceBetween('async function loadStep3Selectable', 'async function refreshStep3State')

    expect(load).toContain('search_field: step3SearchField.value')
    expect(load).toContain('source_name: step3AdvancedSourceName.value.trim() || undefined')
    expect(load).toContain('source_hostname: step3AdvancedHostname.value.trim() || undefined')
    expect(load).toContain('source_ip: step3AdvancedIp.value.trim() || undefined')
    expect(load).toContain('source_status: step3SourceStatus.value || undefined')
    expect(load).toContain('availability: step3Availability.value || undefined')
    expect(load).toContain('running_task: step3RunningTask.value || undefined')
    expect(load).toContain('backup_policy_id: step3BackupPolicyId.value || undefined')
    expect(load).toContain('file_filter_rule_id: step3FileFilterRuleId.value || undefined')
    expect(load).toContain('repository_id: step3RepositoryId.value || undefined')
  })

  it('does not filter the active Step 3 server page in the frontend', () => {
    const filtered = sourceBetween('const filteredStep3SourceList', 'const paginatedStep2SourceList')

    expect(filtered).toContain('if (flowMainStep.value === 2)')
    expect(filtered).toContain('step3SourceList.value')
    expect(filtered.indexOf('step3SourceList.value')).toBeLessThan(filtered.indexOf('flowStep3FiltersMatch'))
    expect(page).toContain(':total="step3SelectableCount"')
    expect(page).not.toContain(':total="step3SelectableCount || filteredStep3SourceList.length"')
  })

  it('resets page one and reloads when any Step 3 filter changes', () => {
    const watcher = sourceBetween(
      'step3SourceStatus.value,\n    step3Availability.value',
      'const STEP3_REFRESH_IDLE_MS',
    )

    expect(watcher).toContain('step3RepositoryId.value')
    expect(watcher).toContain('flowStep2Pager.page = 1')
    expect(watcher).toContain('void refreshFlowStepData(2)')
  })

  it('uses the Tasks-style field prefix and explains NAS Proxy semantics', () => {
    expect(page).toContain('v-model="step3SearchField"')
    expect(page).toContain('#prepend')
    expect(page).toContain("t('protection.backupsPage.step3NasProxyHelp')")
    expect(locale).toContain('For NAS sources, Hostname and IP identify the bound execution Proxy')
  })
})
