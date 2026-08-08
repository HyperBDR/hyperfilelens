import { describe, expect, it } from 'vitest'
import { platformOpsRouteViewKey } from './platformOpsRouteViewKey'

describe('platformOpsRouteViewKey', () => {
  it('keeps Engine layout mounted across AI Models child navigations', () => {
    const engineRecord = { path: 'engine' }
    const leaf = { path: 'ai-settings/add' }
    expect(
      platformOpsRouteViewKey({
        path: '/platform-ops/engine/ai-settings',
        matched: [{ path: '/platform-ops' }, engineRecord, { path: 'ai-settings' }],
      }),
    ).toBe('engine')
    expect(
      platformOpsRouteViewKey({
        path: '/platform-ops/engine/ai-settings/add',
        matched: [{ path: '/platform-ops' }, engineRecord, leaf],
      }),
    ).toBe('engine')
  })

  it('remounts when switching between distinct shell children', () => {
    expect(
      platformOpsRouteViewKey({
        path: '/platform-ops/platform/runtime-environment',
        matched: [
          { path: '/platform-ops' },
          { path: 'platform/runtime-environment' },
        ],
      }),
    ).toBe('platform/runtime-environment')
  })
})
