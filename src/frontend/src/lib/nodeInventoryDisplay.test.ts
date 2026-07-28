import { describe, expect, it } from 'vitest'
import { proxyNodeStackIpLine } from './nodeInventoryDisplay'

describe('node host IP display', () => {
  it('prefers the bound Node host IP over a stale cached fallback', () => {
    expect(
      proxyNodeStackIpLine(
        { ip_address: '10.20.1.15' },
        '203.0.113.20',
      ),
    ).toBe('10.20.1.15')
  })

  it('uses the cached fallback only when no Node host IP is available', () => {
    expect(proxyNodeStackIpLine({ ip_address: null }, '10.20.1.15')).toBe('10.20.1.15')
  })
})
