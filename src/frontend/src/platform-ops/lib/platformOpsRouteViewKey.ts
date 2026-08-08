import type { RouteLocationNormalizedLoaded } from 'vue-router'

/**
 * Suspense remount key for Platform Ops shell children.
 *
 * Use the shell's direct child record (e.g. ``engine``), not the leaf path, so
 * nested layouts like PlatformEngineLayout stay mounted across AI Models →
 * add/edit and do not flap ``lensApiScope`` via onUnmounted.
 */
export function platformOpsRouteViewKey(
  route: Pick<RouteLocationNormalizedLoaded, 'matched' | 'path'>,
): string {
  const shellChild = route.matched[1]
  if (shellChild?.path) {
    return shellChild.path
  }
  return route.path
}
