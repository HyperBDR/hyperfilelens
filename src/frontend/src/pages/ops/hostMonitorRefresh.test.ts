import { describe, expect, it } from 'vitest'
import { resolveHostMonitorRefreshTarget } from './hostMonitorRefresh'

const presets = [
  { value: '1h', hours: 1 },
  { value: '24h', hours: 24 },
]

describe('resolveHostMonitorRefreshTarget', () => {
  it('keeps a valid custom time range', () => {
    expect(resolveHostMonitorRefreshTarget(
      'custom',
      { start: '2026-07-20T00:00', end: '2026-07-21T00:00' },
      presets,
    )).toEqual({ kind: 'custom' })
  })

  it('falls back to 24 hours after the custom range is cleared', () => {
    expect(resolveHostMonitorRefreshTarget(
      'custom',
      { start: '', end: '' },
      presets,
    )).toEqual({ kind: 'preset', value: '24h', hours: 24 })
  })

  it('refreshes the currently selected preset', () => {
    expect(resolveHostMonitorRefreshTarget(
      '1h',
      { start: '', end: '' },
      presets,
    )).toEqual({ kind: 'preset', value: '1h', hours: 1 })
  })
})
