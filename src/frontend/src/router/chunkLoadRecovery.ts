const STORAGE_KEY_PREFIX = 'hyperfilelens:chunk-load-recovery:'

const dynamicImportErrorPatterns = [
  /failed to fetch dynamically imported module/i,
  /importing a module script failed/i,
  /failed to load module script/i,
  /error loading dynamically imported module/i,
  /vite:preloaderror/i,
]

function currentPageKey(location: Pick<Location, 'pathname' | 'search'> = window.location): string {
  return `${location.pathname}${location.search}`
}

function storageKey(pageKey: string): string {
  return `${STORAGE_KEY_PREFIX}${pageKey}`
}

export function isDynamicImportFailure(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return dynamicImportErrorPatterns.some((pattern) => pattern.test(message))
}

/**
 * Reload once for a failed lazy-loaded page. The key is page-specific so a
 * persistent failure cannot create a reload loop, while another route can
 * still recover after a later deployment.
 */
export function reloadOnceForChunkLoadFailure(
  pageKey = currentPageKey(),
  storage: Storage = window.sessionStorage,
  reload: () => void = () => window.location.reload(),
): boolean {
  try {
    const key = storageKey(pageKey)
    if (storage.getItem(key) === '1') return false
    storage.setItem(key, '1')
    reload()
    return true
  } catch {
    return false
  }
}

export function clearChunkLoadFailureAttempt(
  pageKey = currentPageKey(),
  storage: Storage = window.sessionStorage,
): void {
  try {
    storage.removeItem(storageKey(pageKey))
  } catch {
    // Private browsing or a disabled storage API must not affect navigation.
  }
}
