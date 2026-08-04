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

describe('restore snapshot list freshness', () => {
  it('invalidates selected-source state before opening a new restore session', () => {
    const opener = sourceBetween(
      'function openRecoveryWithBackupIds',
      'function openRecoveryForSource',
    )
    const invalidation = sourceBetween(
      'function invalidateRecoverySnapshotLists',
      'function recoverySnapshotListState',
    )

    expect(opener).toContain('invalidateRecoverySnapshotLists(backupIds)')
    expect(opener.indexOf('invalidateRecoverySnapshotLists(backupIds)'))
      .toBeLessThan(opener.indexOf('recOpen.value = true'))
    expect(invalidation).toContain('recoverySnapshotSourceKey(backupSourceHostId(backupId))')
    expect(invalidation).toContain('delete recoverySnapshotLists[sourceKey]')
    expect(invalidation).toContain('recoveryPlanSnapshotMap.value = {}')
  })

  it('recreates invalidated state and reloads snapshots from page one', () => {
    const stateFactory = sourceBetween(
      'function recoverySnapshotListState',
      'function recoverySnapshotListStateForHost',
    )
    const loader = sourceBetween(
      'async function loadRecoverySnapshotsForSource',
      'function sourceSnapshotFallbackOptions',
    )

    expect(stateFactory).toContain('page: 0')
    expect(stateFactory).toContain('loaded: false')
    expect(loader).toContain('const reset = opts.reset || !state.loaded')
    expect(loader).toContain('const nextPage = reset ? 1 : state.page + 1')
    expect(loader).toContain('state.items = reset ? result.results : mergeSnapshotListItems')
  })
})
