import { describe, expect, it } from 'vitest'
import { platformOpsRoutes } from './routes'

describe('platformOpsRoutes', () => {
  it('redirects the retired Data Connections URL to Platform Integrations', () => {
    const engine = platformOpsRoutes.find((route) => route.path === 'engine')
    const legacyRoute = engine?.children?.find(
      (route) => route.path === 'data-connections',
    )

    expect(legacyRoute).toEqual({
      path: 'data-connections',
      redirect: '/platform-ops/platform/integrations',
    })
  })
})
