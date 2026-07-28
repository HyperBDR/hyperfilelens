import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(process.cwd(), 'src/platform-ops/pages/monitoring/MonitoringHost.vue'), 'utf8')
const mobileRules = source.match(/@media \(max-width: 768px\) \{([\s\S]*?)\n\}/)?.[1] || ''

describe('Admin Host Monitor responsive layout', () => {
  it('removes the desktop host flex basis on mobile', () => {
    expect(mobileRules).toContain('flex: 0 1 auto')
    expect(mobileRules).toContain('width: 100%')
  })

  it('keeps the time range visible beside the refresh action', () => {
    expect(mobileRules).toContain('.platform-host-monitor__time-range')
    expect(mobileRules).toContain('flex: 1')
    expect(mobileRules).toContain('min-width: 0')
    expect(mobileRules).toContain('.hfl-date-time-range-picker__trigger')
    expect(mobileRules).toContain('min-height: 44px !important')
    expect(mobileRules).toContain('.platform-host-monitor__toolbar-tail .hfl-refresh-button.el-button')
    expect(mobileRules).toContain('min-width: 44px')
    expect(mobileRules).toContain('height: 44px !important')
  })

  it('uses compact empty charts without changing the tenant monitor component', () => {
    expect(mobileRules).toContain('.platform-host-monitor :deep(.chart-card:has(> .chart-card__empty))')
    expect(mobileRules).toContain('min-height: 180px')
    expect(mobileRules).toContain('.platform-host-monitor :deep(.chart-card__empty)')
    expect(mobileRules).toContain('min-height: 132px')
  })

  it('binds the network selection update exactly once', () => {
    expect(source.match(/@update:selected-network=/g)).toHaveLength(1)
  })
})
