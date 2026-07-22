// @vitest-environment jsdom

import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { en } from '../../../locales/en'
import Overview from './Overview.vue'
import { fetchPlatformOverview, type PlatformOverviewPayload } from '../../lib/platformOpsApi'

vi.mock('echarts/core', () => ({ use: vi.fn() }))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))
vi.mock('echarts/charts', () => ({ LineChart: {} }))
vi.mock('echarts/components', () => ({
  GridComponent: {},
  LegendComponent: {},
  TooltipComponent: {},
}))
vi.mock('vue-echarts', () => ({ default: defineComponent({ template: '<div class="chart-stub" />' }) }))
vi.mock('../../lib/platformOpsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/platformOpsApi')>()
  return { ...actual, fetchPlatformOverview: vi.fn() }
})

const response: PlatformOverviewPayload = {
  range_hours: 24,
  generated_at: '2026-07-22T01:00:00Z',
  metrics: {
    organizations_active: 8,
    alerts_firing: 3,
    alerts_acknowledged: 1,
    tasks_running: 2,
    tasks_failed_in_range: 4,
    nodes_offline: 1,
    outdated_agents: 2,
    repositories_at_risk: 1,
    repositories_capacity_warning: 1,
    repository_max_usage_percent: 84.5,
    notifications_failed_in_range: 2,
    expiring_accounts: 1,
    ai_success_rate: 98.7,
  },
  system_health: {
    overall_status: 'healthy',
    healthy_count: 5,
    degraded_count: 0,
    unavailable_count: 0,
    checked_at: '2026-07-22T01:00:00Z',
    services: [
      { key: 'api', label: 'API', status: 'healthy', detail: '' },
      { key: 'database', label: 'Database', status: 'healthy', detail: '2 ms' },
    ],
  },
  activity_series: [
    { started_at: '2026-07-22T00:00:00Z', alerts: 1, failed_tasks: 2 },
  ],
  recent_alerts: [],
  recent_failed_tasks: [],
}

describe('Admin Overview', () => {
  beforeEach(() => {
    vi.mocked(fetchPlatformOverview).mockResolvedValue(response)
  })

  it('loads the 24-hour overview and renders operational metrics', async () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'en',
      messages: { en },
      missingWarn: false,
      fallbackWarn: false,
    })
    const wrapper = mount(Overview, {
      global: {
        plugins: [i18n, ElementPlus],
        stubs: {
          ModulePage: { template: '<main><slot /></main>' },
          RouterLink: { template: '<a><slot /></a>' },
          VChart: true,
        },
      },
    })

    await flushPromises()

    expect(fetchPlatformOverview).toHaveBeenCalledWith(24)
    expect(wrapper.text()).toContain('Platform Operational')
    expect(wrapper.text()).toContain('Firing Incidents')
    expect(wrapper.text()).toContain('98.7%')
    expect(wrapper.findAll('.overview-kpi-card')).toHaveLength(4)

    await wrapper.get('.hfl-refresh-button').trigger('click')
    await flushPromises()
    expect(fetchPlatformOverview).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
