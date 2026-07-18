import { ref } from 'vue'
import {
  listBackupSelectableSources,
  revertBackupSourcePipelineStep,
  setBackupSourcePipelineStep,
  type BackupSelectableSource,
  type BackupPipelineStep,
} from '../lib/sourceApi'
import { apiErrorMessage } from '../lib/api'
import {
  clearLegacyStep2Sources,
  isBackupSelectableId,
  readLegacyRealStep2Sources,
} from './useDemoFlowStep2Sources'

function normalizeSourceIdList(ids: string[]) {
  const seen = new Set<string>()
  return ids.filter((id) => {
    if (!id || seen.has(id)) return false
    seen.add(id)
    return true
  })
}

function isPipelineMoveBackwardsError(err: unknown) {
  return apiErrorMessage(err, '').includes('pipeline step cannot move backwards')
}

/** Real backup-selectable sources by backend-persisted pipeline step. */
export function useBackupSourcePipeline() {
  const pipelineStep2PlusIds = ref<string[]>([])
  const pipelineStep2Ids = ref<string[]>([])
  const pipelineStep3Ids = ref<string[]>([])
  const pipelineStep2Count = ref(0)
  const pipelineStep3Count = ref(0)
  const pipelineReady = ref(false)

  async function listPipelineRows(step: BackupPipelineStep, signal?: AbortSignal) {
    const pageSize = 100
    const rows: BackupSelectableSource[] = []
    let page = 1
    let total = 0
    do {
      const list = await listBackupSelectableSources({ step, page, page_size: pageSize }, { signal })
      rows.push(...list.results)
      total = list.count
      page += 1
    } while (rows.length < total)
    return rows
  }

  function syncPipelineStep2PlusIds() {
    pipelineStep2PlusIds.value = normalizeSourceIdList([
      ...pipelineStep2Ids.value,
      ...pipelineStep3Ids.value,
    ])
  }

  async function refreshPipelineStep2Ids(signal?: AbortSignal) {
    const rows = await listPipelineRows(2, signal)
    pipelineStep2Ids.value = normalizeSourceIdList(rows.map((row) => row.id))
    pipelineStep2Count.value = rows.length
    syncPipelineStep2PlusIds()
  }

  async function refreshPipelineStep3Ids(signal?: AbortSignal) {
    const rows = await listPipelineRows(3, signal)
    pipelineStep3Ids.value = normalizeSourceIdList(rows.map((row) => row.id))
    pipelineStep3Count.value = rows.length
    syncPipelineStep2PlusIds()
  }

  async function refreshPipelineStep2Count(signal?: AbortSignal) {
    const list = await listBackupSelectableSources({ step: 2, page: 1, page_size: 1 }, { signal })
    pipelineStep2Count.value = list.count
  }

  async function refreshPipelineStep3Count(signal?: AbortSignal) {
    const list = await listBackupSelectableSources({ step: 3, page: 1, page_size: 1 }, { signal })
    pipelineStep3Count.value = list.count
  }

  async function refreshPipelineCounts(signal?: AbortSignal) {
    await Promise.all([
      refreshPipelineStep2Count(signal),
      refreshPipelineStep3Count(signal),
    ])
  }

  async function refreshPipelineStep2PlusIds(signal?: AbortSignal) {
    await Promise.all([
      refreshPipelineStep2Ids(signal),
      refreshPipelineStep3Ids(signal),
    ])
  }

  async function setPipelineStep(ids: string[], step: BackupPipelineStep) {
    const realIds = normalizeSourceIdList(ids.filter(isBackupSelectableId))
    if (!realIds.length) return []
    const result = await setBackupSourcePipelineStep({ ids: realIds, step })
    await refreshPipelineCounts()
    return result.updated
  }

  async function revertPipelineStep(ids: string[], targetStep: 1 | 2) {
    const realIds = normalizeSourceIdList(ids.filter(isBackupSelectableId))
    if (!realIds.length) return []
    const result = await revertBackupSourcePipelineStep({ ids: realIds, target_step: targetStep })
    await refreshPipelineCounts()
    return result.updated
  }

  async function bootstrapPipeline() {
    const legacyReal = readLegacyRealStep2Sources()
    try {
      if (legacyReal.length) {
        await setPipelineStep(legacyReal, 2)
      }
    } catch (err) {
      if (!isPipelineMoveBackwardsError(err)) throw err
    } finally {
      clearLegacyStep2Sources()
    }
    await refreshPipelineCounts()
    pipelineReady.value = true
  }

  return {
    pipelineStep2PlusIds,
    pipelineStep2Ids,
    pipelineStep3Ids,
    pipelineStep2Count,
    pipelineStep3Count,
    pipelineReady,
    refreshPipelineStep2Ids,
    refreshPipelineStep2PlusIds,
    refreshPipelineStep3Ids,
    refreshPipelineStep2Count,
    refreshPipelineStep3Count,
    refreshPipelineCounts,
    setPipelineStep,
    revertPipelineStep,
    bootstrapPipeline,
  }
}
