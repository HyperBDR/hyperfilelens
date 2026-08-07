import { computed, onScopeDispose, ref } from 'vue'
import { isAbortError } from '../lib/api'
import {
  listBackupSelectableSources,
  type BackupSelectableSource,
} from '../lib/sourceApi'

export const RESTORE_TARGET_PAGE_SIZE = 100
export const RESTORE_TARGET_SEARCH_DELAY_MS = 180

const RESTORE_TARGET_BLOCKING_STATUSES = new Set([
  'upgrading',
  'restarting',
  'verifying',
  'verification_pending',
  'removing',
  'cleaning_up',
  'probing',
])

export type RestoreTargetUnavailableReason = 'offline' | 'busy' | null

export type RestoreTargetCatalogOption = {
  source: BackupSelectableSource
  selectable: boolean
  unavailableReason: RestoreTargetUnavailableReason
  pinned: boolean
}

export function restoreTargetUnavailableReason(source: BackupSelectableSource): RestoreTargetUnavailableReason {
  if (source.availability !== 'online') return 'offline'
  return RESTORE_TARGET_BLOCKING_STATUSES.has(source.status) ? 'busy' : null
}

export function restoreTargetIsSelectable(source: BackupSelectableSource) {
  return restoreTargetUnavailableReason(source) === null
}

export function useRestoreTargetCatalog() {
  const rows = ref<BackupSelectableSource[]>([])
  const hydratedRows = ref(new Map<string, BackupSelectableSource>())
  const count = ref(0)
  const page = ref(0)
  const search = ref('')
  const loading = ref(false)
  const loadingMore = ref(false)
  const discoveryError = ref<'initial' | 'more' | null>(null)
  const hydrationError = ref(false)
  const requestedIds = new Set<string>()
  const failedHydrationIds = new Set<string>()
  const hydrationControllers = new Set<AbortController>()
  let activeController: AbortController | null = null
  let requestSeq = 0
  let searchTimer: ReturnType<typeof setTimeout> | null = null

  const allRecords = computed(() => {
    const merged = new Map<string, BackupSelectableSource>()
    for (const row of hydratedRows.value.values()) merged.set(row.id, row)
    for (const row of rows.value) merged.set(row.id, row)
    return [...merged.values()]
  })

  const recordById = computed(() => new Map(allRecords.value.map((row) => [row.id, row])))
  const hasMore = computed(() => rows.value.length < count.value)
  const error = computed<'initial' | 'more' | null>(() => hydrationError.value ? 'initial' : discoveryError.value)

  function cancelSearchTimer() {
    if (!searchTimer) return
    clearTimeout(searchTimer)
    searchTimer = null
  }

  function abortActiveRequest() {
    activeController?.abort()
    activeController = null
  }

  async function loadPage(nextPage: number, reset: boolean) {
    if (!reset && (loading.value || loadingMore.value || !hasMore.value)) return
    if (reset) {
      abortActiveRequest()
      loading.value = true
      loadingMore.value = false
    } else {
      loadingMore.value = true
    }
    const seq = ++requestSeq
    const controller = new AbortController()
    activeController = controller
    if (reset) discoveryError.value = null

    try {
      const result = await listBackupSelectableSources({
        page: nextPage,
        page_size: RESTORE_TARGET_PAGE_SIZE,
        search: search.value || undefined,
        availability: 'online',
      }, { signal: controller.signal })
      if (seq !== requestSeq || controller.signal.aborted) return
      if (reset) {
        rows.value = result.results
      } else {
        const merged = new Map(rows.value.map((row) => [row.id, row]))
        for (const row of result.results) merged.set(row.id, row)
        rows.value = [...merged.values()]
      }
      count.value = result.count
      page.value = nextPage
      discoveryError.value = null
    } catch (err) {
      if (isAbortError(err) || seq !== requestSeq) return
      if (reset) {
        rows.value = []
        count.value = 0
        page.value = 0
        discoveryError.value = 'initial'
      } else {
        discoveryError.value = 'more'
      }
    } finally {
      if (seq === requestSeq) {
        if (activeController === controller) activeController = null
        loading.value = false
        loadingMore.value = false
      }
    }
  }

  async function reset(query = search.value) {
    cancelSearchTimer()
    search.value = query.trim()
    await loadPage(1, true)
  }

  async function loadMore() {
    await loadPage(page.value + 1, false)
  }

  function setSearch(query: string) {
    const normalized = query.trim()
    if (normalized === search.value) {
      if (!rows.value.length && !loading.value && !loadingMore.value) void reset(normalized)
      return
    }
    search.value = normalized
    cancelSearchTimer()
    searchTimer = setTimeout(() => {
      searchTimer = null
      void loadPage(1, true)
    }, RESTORE_TARGET_SEARCH_DELAY_MS)
  }

  async function ensureByIds(ids: string[]) {
    const normalized = [...new Set(ids.map((id) => id.trim()).filter(Boolean))]
    for (const id of normalized) requestedIds.add(id)
    for (const id of normalized) {
      if (recordById.value.has(id)) failedHydrationIds.delete(id)
    }
    hydrationError.value = failedHydrationIds.size > 0
    const missing = normalized.filter((id) => !recordById.value.has(id))
    if (!missing.length) return normalized.map((id) => recordById.value.get(id)).filter(Boolean) as BackupSelectableSource[]

    const chunks: string[][] = []
    for (let offset = 0; offset < missing.length; offset += RESTORE_TARGET_PAGE_SIZE) {
      chunks.push(missing.slice(offset, offset + RESTORE_TARGET_PAGE_SIZE))
    }
    const requests = chunks.map(async (chunk) => {
      const controller = new AbortController()
      hydrationControllers.add(controller)
      try {
        return await listBackupSelectableSources({
          ids: chunk.join(','),
          page_size: RESTORE_TARGET_PAGE_SIZE,
        }, { signal: controller.signal })
      } finally {
        hydrationControllers.delete(controller)
      }
    })
    const results = await Promise.allSettled(requests)
    const next = new Map(hydratedRows.value)
    results.forEach((result, index) => {
      const chunk = chunks[index] ?? []
      if (result.status === 'fulfilled') {
        for (const row of result.value.results) next.set(row.id, row)
        for (const id of chunk) failedHydrationIds.delete(id)
      } else if (!isAbortError(result.reason)) {
        for (const id of chunk) failedHydrationIds.add(id)
      }
    })
    hydratedRows.value = next
    hydrationError.value = failedHydrationIds.size > 0
    return normalized.map((id) => recordById.value.get(id)).filter(Boolean) as BackupSelectableSource[]
  }

  async function retry() {
    const retryKind = error.value
    discoveryError.value = null
    if (retryKind === 'more') await loadMore()
    else await reset(search.value)
    await ensureByIds([...requestedIds])
  }

  function getRecord(id: string) {
    return recordById.value.get(id)
  }

  function isSelectable(id: string) {
    const source = getRecord(id)
    return Boolean(source && restoreTargetIsSelectable(source))
  }

  function options(pinnedIds: string[] = []): RestoreTargetCatalogOption[] {
    const pinned = new Set(pinnedIds.filter(Boolean))
    const ordered = new Map<string, BackupSelectableSource>()
    for (const row of rows.value) ordered.set(row.id, row)
    for (const id of pinned) {
      const row = getRecord(id)
      if (row) ordered.set(id, row)
    }
    return [...ordered.values()].map((source) => ({
      source,
      selectable: restoreTargetIsSelectable(source),
      unavailableReason: restoreTargetUnavailableReason(source),
      pinned: pinned.has(source.id),
    }))
  }

  function dispose() {
    cancelSearchTimer()
    abortActiveRequest()
    for (const controller of hydrationControllers) controller.abort()
    hydrationControllers.clear()
  }

  onScopeDispose(dispose)

  return {
    rows,
    allRecords,
    count,
    page,
    search,
    loading,
    loadingMore,
    error,
    hasMore,
    reset,
    loadMore,
    setSearch,
    ensureByIds,
    retry,
    getRecord,
    isSelectable,
    options,
    dispose,
  }
}
