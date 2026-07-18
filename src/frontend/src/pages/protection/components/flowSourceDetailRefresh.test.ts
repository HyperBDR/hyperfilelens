import { describe, expect, it, vi } from 'vitest'
import {
  refreshFlowSourceDetailTab,
  type FlowSourceDetailTabLoaders,
  type RefreshableFlowSourceDetailTab,
} from './flowSourceDetailRefresh'

describe('refreshFlowSourceDetailTab', () => {
  it.each<RefreshableFlowSourceDetailTab>(['overview', 'snapshots', 'restoreRecords', 'tasks'])(
    'loads fresh %s data on every activation',
    async (tab) => {
      const loaders: FlowSourceDetailTabLoaders = {
        overview: vi.fn(),
        snapshots: vi.fn(),
        restoreRecords: vi.fn(),
        tasks: vi.fn(),
      }

      await refreshFlowSourceDetailTab(tab, loaders)
      await refreshFlowSourceDetailTab(tab, loaders)

      expect(loaders[tab]).toHaveBeenCalledTimes(2)
      for (const [name, loader] of Object.entries(loaders)) {
        expect(loader).toHaveBeenCalledTimes(name === tab ? 2 : 0)
      }
    },
  )
})
