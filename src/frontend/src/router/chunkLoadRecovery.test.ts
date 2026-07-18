import { describe, expect, it } from 'vitest'
import {
  clearChunkLoadFailureAttempt,
  isDynamicImportFailure,
  reloadOnceForChunkLoadFailure,
} from './chunkLoadRecovery'

function createStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() {
      return values.size
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  }
}

describe('chunkLoadRecovery', () => {
  it('recognizes dynamic module loading failures only', () => {
    expect(isDynamicImportFailure(new TypeError('Failed to fetch dynamically imported module'))).toBe(true)
    expect(isDynamicImportFailure(new Error('vite:preloadError: failed to load'))).toBe(true)
    expect(isDynamicImportFailure(new Error('Route guard rejected'))).toBe(false)
  })

  it('reloads once per failed page and clears after the page loads', () => {
    const storage = createStorage()
    let reloads = 0

    expect(reloadOnceForChunkLoadFailure('/insight', storage, () => { reloads += 1 })).toBe(true)
    expect(reloadOnceForChunkLoadFailure('/insight', storage, () => { reloads += 1 })).toBe(false)
    expect(reloads).toBe(1)

    clearChunkLoadFailureAttempt('/insight', storage)
    expect(reloadOnceForChunkLoadFailure('/insight', storage, () => { reloads += 1 })).toBe(true)
    expect(reloads).toBe(2)
  })
})
