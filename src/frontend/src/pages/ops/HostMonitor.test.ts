// @vitest-environment jsdom

import { defineComponent, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import HostMonitor from './HostMonitor.vue'
import { fetchMonitorNodes, fetchNodeMonitor } from '../../lib/monitorApi'

vi.mock('echarts/core', () => ({ use: vi.fn() }))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))
vi.mock('echarts/charts', () => ({ LineChart: {} }))
vi.mock('echarts/components', () => ({
  GridComponent: {},
  LegendComponent: {},
  TooltipComponent: {},
}))
vi.mock('vue-echarts', () => ({ default: defineComponent({ template: '<div />' }) }))
vi.mock('../../composables/useOpsMenus', () => ({ useOpsMenus: () => [] }))
vi.mock('../../composables/useNodeConnectionDisplay', () => ({
  debouncedNodeStatus: ({ status }: { status: string }) => status,
}))
vi.mock('../../composables/useHostMonitorCharts', () => ({
  useHostMonitorCharts: () => ({
    current: ref({}),
    uniqueDiskNames: ref([]),
    uniqueNetworkNames: ref([]),
    totalNetworkBytes: ref({ recv: 0, sent: 0 }),
    cpuOption: ref({ series: [] }),
    loadOption: ref({ series: [] }),
    memoryOption: ref({ series: [] }),
    diskUsageOption: ref({ series: [] }),
    diskThroughputOption: ref({ series: [] }),
    diskIopsOption: ref({ series: [] }),
    networkBytesOption: ref({ series: [] }),
    networkPacketsOption: ref({ series: [] }),
  }),
}))
vi.mock('../../lib/monitorApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/monitorApi')>()
  return {
    ...actual,
    fetchMonitorNodes: vi.fn(),
    fetchNodeMonitor: vi.fn(),
  }
})

const monitorPayload = {
  host: {},
  range: {},
  current: {},
  series: [],
}

describe('HostMonitor refresh button', () => {
  beforeEach(() => {
    vi.mocked(fetchMonitorNodes).mockResolvedValue([{
      id: 7,
      name: 'agent-7',
      role: 'agent',
      status: 'online',
      hostname: 'agent-7',
      platform: 'linux',
    }])
    vi.mocked(fetchNodeMonitor).mockResolvedValue(monitorPayload)
  })

  it('reloads the node list and metrics when clicked', async () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'en',
      messages: { en: {} },
      missingWarn: false,
      fallbackWarn: false,
    })
    const wrapper = mount(HostMonitor, {
      global: {
        plugins: [i18n, ElementPlus],
        stubs: {
          ModulePage: { template: '<main><slot /></main>' },
          ElSelect: true,
          ElOption: true,
          HflDateTimeRangePicker: true,
          OpsStatCard: true,
          VChart: true,
        },
      },
    })
    await flushPromises()
    vi.mocked(fetchMonitorNodes).mockClear()
    vi.mocked(fetchNodeMonitor).mockClear()

    await wrapper.get('.hfl-refresh-button').trigger('click')
    await flushPromises()

    expect(fetchMonitorNodes).toHaveBeenCalledWith('agent')
    expect(fetchNodeMonitor).toHaveBeenCalledWith(7, expect.objectContaining({
      startAt: expect.any(String),
      endAt: expect.any(String),
    }))
    wrapper.unmount()
  })

  it('recovers after the initial node list is empty', async () => {
    vi.mocked(fetchMonitorNodes)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{
        id: 8,
        name: 'agent-8',
        role: 'agent',
        status: 'online',
        hostname: 'agent-8',
        platform: 'linux',
      }])
    const i18n = createI18n({
      legacy: false,
      locale: 'en',
      messages: { en: {} },
      missingWarn: false,
      fallbackWarn: false,
    })
    const wrapper = mount(HostMonitor, {
      global: {
        plugins: [i18n, ElementPlus],
        stubs: {
          ModulePage: { template: '<main><slot /></main>' },
          ElSelect: true,
          ElOption: true,
          HflDateTimeRangePicker: true,
          OpsStatCard: true,
          VChart: true,
        },
      },
    })
    await flushPromises()

    await wrapper.get('.hfl-refresh-button').trigger('click')
    await flushPromises()

    expect(fetchNodeMonitor).toHaveBeenCalledWith(8, expect.any(Object))
    wrapper.unmount()
  })
})
