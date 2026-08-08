import { usePlatformOpsSideNav as useCommunityPlatformOpsSideNav } from './usePlatformOpsSideNav'
import { usePlatformOpsSideNav as useExtPlatformOpsSideNav } from '@ext/platform/platform-ops/composables/usePlatformOpsSideNav'

/**
 * Prefer the platform-extension side nav when present; otherwise community essentials.
 */
export function useResolvedPlatformOpsSideNav() {
  return useExtPlatformOpsSideNav() || useCommunityPlatformOpsSideNav()
}
