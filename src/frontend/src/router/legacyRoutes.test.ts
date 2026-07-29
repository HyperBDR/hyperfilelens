// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { router } from './index'

describe('legacy routes', () => {
  it('redirects the retired Retention page to Backup Policies', () => {
    const retentionRoute = router.getRoutes().find(
      (route) => route.path === '/protection/retention',
    )

    expect(retentionRoute?.redirect).toBe('/protection/policies?tab=backup')
    expect(retentionRoute?.components).toBeUndefined()
  })
})
