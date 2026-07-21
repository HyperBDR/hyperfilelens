import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const page = readFileSync(resolve(process.cwd(), 'src/pages/protection/DataProtection.vue'), 'utf8')
const wizard = readFileSync(resolve(process.cwd(), 'src/pages/protection/BackupCreateWizard.vue'), 'utf8')
const protectionLocale = readFileSync(resolve(process.cwd(), 'src/locales/enProtectionPages.ts'), 'utf8')

function sourceBetween(startMarker: string, endMarker: string) {
  const start = page.indexOf(startMarker)
  const end = page.indexOf(endMarker, start + 1)

  expect(start).toBeGreaterThan(-1)
  expect(end).toBeGreaterThan(start)
  return page.slice(start, end)
}

function functionSource(name: string, nextName: string) {
  return sourceBetween(`function ${name}`, `function ${nextName}`)
}

describe('backup wizard step 3 More Actions refresh', () => {
  it('uses operation-specific loading and saving copy for each edit action', () => {
    const waitingStart = wizard.indexOf('const editorWaitingText')
    const waitingEnd = wizard.indexOf('function hideOptionPopovers', waitingStart)
    const waitingCopy = wizard.slice(waitingStart, waitingEnd)

    expect(waitingStart).toBeGreaterThan(-1)
    expect(waitingEnd).toBeGreaterThan(waitingStart)
    expect(waitingCopy).toContain("t('protection.backupsPage.loadingEditWizard')")
    expect(waitingCopy).toContain("t('protection.backupsPage.waitingEditBackupPaths')")
    expect(waitingCopy).toContain("t('protection.backupsPage.waitingEditBackupPolicy')")
    expect(waitingCopy).toContain("t('protection.backupsPage.waitingEditRestorePlan')")
    expect(waitingCopy).toContain("t('protection.backupsPage.waitingCreate')")
    expect(wizard).toContain(':waiting-text="editorWaitingText"')
    expect(protectionLocale).toContain("waitingEditBackupPaths: 'Saving backup paths…'")
    expect(protectionLocale).toContain("waitingEditBackupPolicy: 'Saving backup policy…'")
    expect(protectionLocale).toContain("waitingEditRestorePlan: 'Saving restore plan…'")
  })

  it('uses save semantics when an edit request fails', () => {
    const editHandlerStart = wizard.indexOf('async function runEditBackupConfig')
    const editHandlerEnd = wizard.indexOf('function submitCreateWizard', editHandlerStart)
    const editHandler = wizard.slice(editHandlerStart, editHandlerEnd)

    expect(editHandler).toContain('apiErrorMessage(err, editorFailureText.value)')
    expect(protectionLocale).toContain("editFailed: 'Failed to save backup configuration'")
  })

  it('does not show a success notification after manually refreshing the step 3 list', () => {
    const refresh = functionSource('refreshTaskLists', 'syncStep3TableSelection')

    expect(refresh).not.toContain('ElMessage.success')
  })

  it('reloads the full step 3 list state after backup configuration edits complete', () => {
    const editStart = wizard.indexOf('async function runEditBackupConfig')
    const editEnd = wizard.indexOf('function submitCreateWizard', editStart)
    const editHandler = wizard.slice(editStart, editEnd)
    const handler = sourceBetween(
      'async function finishCreateAndGoToStep3',
      'const addSourceOpen',
    )

    expect(editStart).toBeGreaterThan(-1)
    expect(editEnd).toBeGreaterThan(editStart)
    expect(editHandler).toContain('emit(\'completed\', editedSourceIds)')
    expect(editHandler).toContain('`${config.source_type}:${config.source_ref_id}`')
    expect(page).toContain('@completed="finishCreateAndGoToStep3"')
    expect(handler).toContain('await refreshStep3AfterMoreAction({ focusIds: requestedFocusIds })')
  })

  it('reloads the full step 3 list state after stopping backup or restore tasks', () => {
    const stopBackup = functionSource('stopSelectedBackupTasks', 'stopSelectedRestoreTasks')
    const stopRestore = functionSource('stopSelectedRestoreTasks', 'onBackupTaskSelection')

    expect(stopBackup).toContain('await refreshStep3AfterMoreAction()')
    expect(stopRestore).toContain('await refreshStep3AfterMoreAction()')
    expect(stopBackup).not.toContain('await refreshStep3State()')
    expect(stopRestore).not.toContain('await refreshStep3State()')
  })

  it('reloads and clears stale selection after reset or unregister succeeds', () => {
    const reset = functionSource('confirmResetBackupConfiguration', 'onBackupSourcesDeleted')
    const unregister = functionSource('onBackupSourcesDeleted', 'deleteSelectedSourcesFromStep1')

    expect(reset).toContain('await clearStep3TableSelection()')
    expect(reset).toContain('await refreshStep3AfterMoreAction({ preserveSelection: false })')
    expect(unregister).toContain('await clearStep3TableSelection()')
    expect(unregister).toContain('refreshStep3AfterMoreAction({ preserveSelection: false })')
  })

  it('waits for an accepted unregister task to reach a terminal state before the final refresh', () => {
    const monitor = functionSource('monitorPendingUnregister', 'affectedBackupIdsForSources')
    const unregister = functionSource('onBackupSourcesDeleted', 'deleteSelectedSourcesFromStep1')

    expect(monitor).toContain('getTask(taskUuid)')
    expect(monitor).toContain("new Set(['success', 'failed', 'cancelled', 'timeout'])")
    expect(monitor).toContain('refreshStep3AfterMoreAction({ preserveSelection: false })')
    expect(unregister).toContain('monitorPendingUnregister(Array.from(idSet), taskUuids)')
  })

  it('refreshes source rows, pipeline membership, configurations, and pagination through one helper', () => {
    const refresh = functionSource('refreshStep3AfterMoreAction', 'finishCreateAndGoToStep3')

    expect(refresh).toContain('pageRequests.nextSignal(scope)')
    expect(refresh).toContain('refreshPipelineStep2PlusIds(signal)')
    expect(refresh).not.toContain('refreshPipelineStep3Ids(signal)')
    expect(refresh).toContain('await loadStep3SelectableWithPageClamp(signal)')
    expect(refresh).toContain('await refreshBackupConfigs(signal)')
    expect(refresh).toContain('pageRequests.isCurrentSignal(scope, signal)')
    expect(refresh).toContain('syncStep3TableSelection()')
  })
})
