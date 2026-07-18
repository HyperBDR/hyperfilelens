// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { useBackupSourcePipeline } from './useBackupSourcePipeline'
import { listBackupSelectableSources } from '../lib/sourceApi'

vi.mock('../lib/sourceApi', () => ({
  listBackupSelectableSources: vi.fn(),
  revertBackupSourcePipelineStep: vi.fn(),
  setBackupSourcePipelineStep: vi.fn(),
}))

vi.mock('./useDemoFlowStep2Sources', () => ({
  clearLegacyStep2Sources: vi.fn(),
  isBackupSelectableId: vi.fn(() => true),
  readLegacyRealStep2Sources: vi.fn(() => []),
}))

afterEach(() => {
  vi.clearAllMocks()
})

describe('useBackupSourcePipeline', () => {
  it('loads step 2 and step 3 totals without filtering step 3 by online status', async () => {
    vi.mocked(listBackupSelectableSources).mockImplementation(async (params) => ({
      count: params?.step === 2 ? 4 : 7,
      results: [],
    }))

    const pipeline = useBackupSourcePipeline()
    await pipeline.bootstrapPipeline()

    expect(listBackupSelectableSources).toHaveBeenCalledTimes(2)
    expect(listBackupSelectableSources).toHaveBeenCalledWith(
      { step: 2, page: 1, page_size: 1 },
      { signal: undefined },
    )
    expect(listBackupSelectableSources).toHaveBeenCalledWith(
      { step: 3, page: 1, page_size: 1 },
      { signal: undefined },
    )
    expect(pipeline.pipelineStep2Count.value).toBe(4)
    expect(pipeline.pipelineStep3Count.value).toBe(7)
  })
})
