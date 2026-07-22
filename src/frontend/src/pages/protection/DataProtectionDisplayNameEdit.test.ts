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

describe('backup wizard display name editing', () => {
  it('adds Edit Display Name to all three More Actions menus', () => {
    expect(page.match(/flowActionEditDisplayName/g)).toHaveLength(3)
    expect(page).toContain('@click="openStep1DisplayNameEditor"')
    expect(page).toContain('@click="openStep2DisplayNameEditor"')
    expect(page).toContain('@click="openStep3DisplayNameEditor"')
    expect(protectionLocale).toContain("flowActionEditDisplayName: 'Edit Display Name'")
  })

  it('places the display name action before the existing first action in every menu', () => {
    const step1Menu = sourceBetween('@click="openStep1DisplayNameEditor"', '@click="deleteSelectedSourcesFromStep1"')
    const step2Menu = sourceBetween('@click="openStep2DisplayNameEditor"', '@click="deleteSelectedSourcesFromStep2"')
    const step3Menu = sourceBetween('@click="openStep3DisplayNameEditor"', "@click=\"openBackupConfigEditFromStep3('paths')\"")

    expect(step1Menu).toContain('flowActionEditDisplayName')
    expect(step2Menu).toContain('flowActionEditDisplayName')
    expect(step3Menu).toContain('flowActionEditDisplayName')
  })

  it('uses the existing per-source update API for hosts and NAS sources', () => {
    const updateHandler = sourceBetween(
      'async function updateBackupSourceDisplayName',
      'async function refreshAfterDisplayNameEdit',
    )

    expect(updateHandler).toContain("parsed.type === 'agent'")
    expect(updateHandler).toContain('await updateNode(parsed.refId, { name })')
    expect(updateHandler).toContain("parsed.type === 'nas'")
    expect(updateHandler).toContain('await updateSourceResource(parsed.refId, { name })')
  })

  it('submits changed rows in bounded batches and retains failed rows', () => {
    const submitHandler = sourceBetween(
      'async function submitDisplayNameEdit',
      'const step3SourceActionsEnabled',
    )

    expect(page).toContain('const DISPLAY_NAME_EDIT_BATCH_SIZE = 5')
    expect(submitHandler).toContain('index += DISPLAY_NAME_EDIT_BATCH_SIZE')
    expect(submitHandler).toContain('Promise.allSettled')
    expect(submitHandler).toContain('displayNameEditRows.value = failed')
    expect(submitHandler).toContain('refreshAfterDisplayNameEdit(step, Array.from(succeeded))')
  })

  it('states that only the display name changes and applies per-type limits', () => {
    expect(page).toContain("row.source.type === 'host' ? 200 : 255")
    expect(page).toContain(':maxlength="displayNameEditMaxLength(row)"')
    expect(page).toContain(':error="displayNameEditError(row)"')
    expect(protectionLocale).toContain('Only the display name will change. Endpoints and backup settings remain unchanged.')
  })
})
