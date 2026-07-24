import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(process.cwd(), 'src/pages/ops/HostMonitor.vue'), 'utf8')

describe('HostMonitor responsive empty charts', () => {
  it('compacts only empty chart cards on phones', () => {
    const mobileStyles = source.slice(source.indexOf('@media (max-width: 768px)'))

    expect(mobileStyles).toContain('.chart-card:has(> .chart-card__empty)')
    expect(mobileStyles).toContain('min-height: 180px')
    expect(mobileStyles).toContain('.chart-card__empty')
    expect(mobileStyles).toContain('min-height: 132px')
  })
})
