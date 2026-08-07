// @vitest-environment jsdom

import { effectScope, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { listBackupSelectableSources, type BackupSelectableSource } from '../lib/sourceApi'
import {
  RESTORE_TARGET_SEARCH_DELAY_MS,
  restoreTargetIsSelectable,
  useRestoreTargetCatalog,
} from './useRestoreTargetCatalog'

vi.mock('../lib/sourceApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/sourceApi')>()
  return { ...actual, listBackupSelectableSources: vi.fn() }
})

const listMock = vi.mocked(listBackupSelectableSources)

function source(id: string, overrides: Partial<BackupSelectableSource> = {}): BackupSelectableSource {
  const [kind, refId] = id.split(':')
  return {
    id,
    kind: kind === 'nas' ? 'nas' : 'agent',
    ref_id: Number(refId),
    type: kind === 'nas' ? 'nas' : 'host',
    name: id,
    hostname: id,
    node_name: id,
    node_ip: '192.0.2.1',
    status: 'active',
    availability: 'online',
    ...overrides,
  }
}

function catalog() {
  const scope = effectScope()
  const value = scope.run(() => useRestoreTargetCatalog())
  if (!value) throw new Error('catalog scope was not created')
  return { scope, value }
}

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('useRestoreTargetCatalog', () => {
  it('uses the online paged contract and deduplicates subsequent pages', async () => {
    listMock
      .mockResolvedValueOnce({ count: 3, results: [source('agent:1'), source('agent:2')] })
      .mockResolvedValueOnce({ count: 3, results: [source('agent:2'), source('nas:3')] })
    const { scope, value } = catalog()

    await value.reset(' target ')
    await value.loadMore()

    expect(listMock).toHaveBeenNthCalledWith(1, {
      page: 1,
      page_size: 100,
      search: 'target',
      availability: 'online',
    }, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(listMock).toHaveBeenNthCalledWith(2, {
      page: 2,
      page_size: 100,
      search: 'target',
      availability: 'online',
    }, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(value.rows.value.map((row) => row.id)).toEqual(['agent:1', 'agent:2', 'nas:3'])
    expect(value.hasMore.value).toBe(false)
    scope.stop()
  })

  it('debounces search and keeps only the latest response', async () => {
    vi.useFakeTimers()
    let resolveOld!: (value: { count: number; results: BackupSelectableSource[] }) => void
    listMock
      .mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve }))
      .mockResolvedValueOnce({ count: 1, results: [source('agent:2')] })
    const { scope, value } = catalog()

    const oldRequest = value.reset('old')
    value.setSearch('new')
    await vi.advanceTimersByTimeAsync(RESTORE_TARGET_SEARCH_DELAY_MS)
    resolveOld({ count: 1, results: [source('agent:1')] })
    await oldRequest
    await nextTick()

    expect(value.rows.value.map((row) => row.id)).toEqual(['agent:2'])
    expect(value.search.value).toBe('new')
    scope.stop()
  })

  it('distinguishes request failure from an empty result and retries', async () => {
    listMock
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ count: 0, results: [] })
    const { scope, value } = catalog()

    await value.reset()
    expect(value.error.value).toBe('initial')
    await value.retry()
    expect(value.error.value).toBeNull()
    expect(value.rows.value).toEqual([])
    scope.stop()
  })

  it('keeps prior rows when loading another page fails', async () => {
    listMock
      .mockResolvedValueOnce({ count: 2, results: [source('agent:1')] })
      .mockRejectedValueOnce(new Error('network'))
    const { scope, value } = catalog()

    await value.reset()
    await value.loadMore()

    expect(value.rows.value.map((row) => row.id)).toEqual(['agent:1'])
    expect(value.error.value).toBe('more')
    scope.stop()
  })

  it('hydrates and pins an unavailable saved target without making it selectable', async () => {
    listMock.mockResolvedValue({ count: 1, results: [source('nas:7', { availability: 'offline' })] })
    const { scope, value } = catalog()

    await value.ensureByIds(['nas:7'])
    const options = value.options(['nas:7'])

    expect(listMock).toHaveBeenCalledWith({ ids: 'nas:7', page_size: 100 }, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(options).toHaveLength(1)
    expect(options[0]).toMatchObject({ selectable: false, unavailableReason: 'offline', pinned: true })
    scope.stop()
  })

  it('hydrates more than one API page of exact IDs in bounded batches', async () => {
    const ids = Array.from({ length: 101 }, (_, index) => `agent:${index + 1}`)
    listMock
      .mockResolvedValueOnce({ count: 100, results: ids.slice(0, 100).map((id) => source(id)) })
      .mockResolvedValueOnce({ count: 1, results: [source(ids[100]!)] })
    const { scope, value } = catalog()

    const rows = await value.ensureByIds(ids)

    expect(listMock).toHaveBeenCalledTimes(2)
    expect(listMock.mock.calls[0]?.[0]).toMatchObject({ page_size: 100 })
    expect(listMock.mock.calls[1]?.[0]).toEqual({ ids: 'agent:101', page_size: 100 })
    expect(rows).toHaveLength(101)
    scope.stop()
  })

  it('keeps a hydration failure visible until the missing target retries successfully', async () => {
    listMock
      .mockRejectedValueOnce(new Error('hydration failed'))
      .mockResolvedValueOnce({ count: 0, results: [] })
      .mockResolvedValueOnce({ count: 0, results: [] })
      .mockResolvedValueOnce({ count: 1, results: [source('nas:7', { availability: 'offline' })] })
    const { scope, value } = catalog()

    await value.ensureByIds(['nas:7'])
    await value.reset()
    expect(value.error.value).toBe('initial')

    await value.retry()
    expect(value.error.value).toBeNull()
    expect(value.options(['nas:7'])[0]).toMatchObject({ selectable: false, pinned: true })
    scope.stop()
  })

  it('retries a failed next page without discarding prior rows', async () => {
    listMock
      .mockResolvedValueOnce({ count: 2, results: [source('agent:1')] })
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ count: 2, results: [source('agent:2')] })
    const { scope, value } = catalog()

    await value.reset()
    await value.loadMore()
    await value.retry()

    expect(listMock).toHaveBeenNthCalledWith(3, {
      page: 2,
      page_size: 100,
      search: undefined,
      availability: 'online',
    }, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(value.rows.value.map((row) => row.id)).toEqual(['agent:1', 'agent:2'])
    scope.stop()
  })

  it('prefers a fresh discovery row over an older hydrated copy', async () => {
    listMock
      .mockResolvedValueOnce({ count: 1, results: [source('agent:1', { availability: 'offline' })] })
      .mockResolvedValueOnce({ count: 1, results: [source('agent:1', { availability: 'online' })] })
    const { scope, value } = catalog()

    await value.ensureByIds(['agent:1'])
    await value.reset()

    expect(value.isSelectable('agent:1')).toBe(true)
    expect(value.options(['agent:1'])[0]?.source.availability).toBe('online')
    scope.stop()
  })

  it('rejects online targets owned by a blocking lifecycle operation', () => {
    expect(restoreTargetIsSelectable(source('agent:1'))).toBe(true)
    expect(restoreTargetIsSelectable(source('agent:1', { status: 'upgrading' }))).toBe(false)
    expect(restoreTargetIsSelectable(source('agent:1', { status: 'probing' }))).toBe(false)
  })
})
