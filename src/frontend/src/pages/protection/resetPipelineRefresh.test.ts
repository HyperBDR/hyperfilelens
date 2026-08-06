import { describe, expect, it } from 'vitest'
import {
  selectFinishedResetSourceIds,
  selectTerminalFailedResetSourceIds,
} from './resetPipelineRefresh'

describe('resetPipelineRefresh', () => {
  it('treats cleared reset state as finished regardless of step-3 page membership', () => {
    expect(
      selectFinishedResetSourceIds(
        ['nas:1', 'nas:2'],
        (id) => (id === 'nas:2' ? 'resetting' : ''),
      ),
    ).toEqual(['nas:1'])
  })

  it('does not treat off-page resetting sources as finished', () => {
    expect(
      selectFinishedResetSourceIds(
        ['nas:1'],
        () => 'resetting',
      ),
    ).toEqual([])
  })

  it('does not treat reset_failed as finished for pipeline refresh', () => {
    expect(
      selectFinishedResetSourceIds(
        ['nas:1'],
        () => 'reset_failed',
      ),
    ).toEqual([])
  })

  it('identifies terminal reset_failed sources for tracking cleanup', () => {
    expect(
      selectTerminalFailedResetSourceIds(
        ['nas:1', 'nas:2'],
        (id) => (id === 'nas:1' ? 'reset_failed' : 'resetting'),
      ),
    ).toEqual(['nas:1'])
  })
})
