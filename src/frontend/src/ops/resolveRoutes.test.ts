import { beforeEach, describe, expect, it, vi } from 'vitest'

const routeState = vi.hoisted(() => ({
  tenantOpsRoutes: [] as Array<Record<string, unknown>>,
}))

vi.mock('@ext/platform/ops/routes', () => ({
  get tenantOpsRoutes() {
    return routeState.tenantOpsRoutes
  },
}))

describe('resolveTenantOpsRoutes', () => {
  beforeEach(() => {
    routeState.tenantOpsRoutes = []
  })

  it('contributes no tenant ops routes when the extension stub is empty', async () => {
    const { resolveTenantOpsRoutes } = await import('./resolveRoutes')
    expect(resolveTenantOpsRoutes()).toEqual([])
  })

  it('forwards host-monitor when the platform extension contributes it', async () => {
    routeState.tenantOpsRoutes = [{ path: 'ops/host-monitor', component: {} }]
    const { resolveTenantOpsRoutes } = await import('./resolveRoutes')
    const routes = resolveTenantOpsRoutes()
    expect(routes.some((route) => route.path === 'ops/host-monitor')).toBe(true)
  })
})
