import { platformOpsRoutes as communityPlatformOpsRoutes } from './routes'
import { platformOpsRoutes as extPlatformOpsRoutes } from '@ext/platform/platform-ops/routes'

type RouteLike = { path?: string; children?: RouteLike[] }

function hasPath(routes: RouteLike[], path: string): boolean {
  return routes.some((route) => route.path === path)
}

/**
 * With platform extension: full ops console + Host essential settings.
 * Community (empty socket): Host settings shell only.
 */
export function resolvePlatformOpsRoutes() {
  const extRoutes = (extPlatformOpsRoutes || []) as RouteLike[]
  if (!extRoutes.length) {
    return communityPlatformOpsRoutes
  }

  const community = communityPlatformOpsRoutes as RouteLike[]
  const merged = [...extRoutes]

  for (const route of community) {
    if (!route.path || route.path === '' || route.path === 'engine') continue
    if (!hasPath(merged, route.path)) {
      merged.push(route)
    }
  }

  const extEngine = merged.find((route) => route.path === 'engine')
  const communityEngine = community.find((route) => route.path === 'engine')
  if (extEngine && communityEngine?.children) {
    const children = [...(extEngine.children || [])]
    for (const child of communityEngine.children) {
      if (!child.path || hasPath(children, child.path)) continue
      children.push(child)
    }
    extEngine.children = children
  } else if (!extEngine && communityEngine) {
    merged.push(communityEngine)
  }

  // Prefer AI Models home only when extension has no overview.
  if (!hasPath(merged, 'overview')) {
    const empty = merged.find((route) => route.path === '')
    if (empty && 'redirect' in empty) {
      ;(empty as { redirect: string }).redirect = '/platform-ops/engine/ai-settings'
    }
  }

  return merged
}
