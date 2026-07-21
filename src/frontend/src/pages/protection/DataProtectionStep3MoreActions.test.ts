import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const page = readFileSync(resolve(process.cwd(), 'src/pages/protection/DataProtection.vue'), 'utf8')

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
  it('reloads the full step 3 list state after backup configuration edits complete', () => {
    const handler = sourceBetween(
      'async function finishCreateAndGoToStep3',
      'const addSourceOpen',
    )

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

  it('refreshes source rows, pipeline membership, configurations, and pagination through one helper', () => {
    const refresh = functionSource('refreshStep3AfterMoreAction', 'finishCreateAndGoToStep3')

    expect(refresh).toContain('refreshPipelineStep2PlusIds()')
    expect(refresh).toContain('refreshPipelineStep3Ids()')
    expect(refresh).toContain('await loadStep3SelectableWithPageClamp()')
    expect(refresh).toContain('await refreshBackupConfigs()')
    expect(refresh).toContain('syncStep3TableSelection()')
  })
})
