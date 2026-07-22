import { describe, expect, it } from 'vitest'
import { platformOpsRoutes } from './routes'

describe('Admin Monitoring navigation', () => {
  it('exposes the complete Monitoring information architecture in order', () => {
    const paths = platformOpsRoutes.map((route) => route.path)
    const monitoringPaths = paths.filter((path) => path.startsWith('monitoring/'))

    expect(monitoringPaths).toEqual([
      'monitoring/incidents',
      'monitoring/system-health',
      'monitoring/host',
      'monitoring/tasks',
      'monitoring/nodes',
      'monitoring/notification-deliveries',
      'monitoring/notifications',
    ])
  })

  it('keeps legacy Monitoring URLs as redirects', () => {
    const legacyHost = platformOpsRoutes.find((route) => route.path === 'monitoring/host')
    const legacyNotifications = platformOpsRoutes.find(
      (route) => route.path === 'monitoring/notifications',
    )

    expect(legacyHost?.redirect).toBe('/platform-ops/monitoring/system-health')
    expect(legacyNotifications?.redirect).toBe(
      '/platform-ops/monitoring/notification-deliveries',
    )
  })
})
