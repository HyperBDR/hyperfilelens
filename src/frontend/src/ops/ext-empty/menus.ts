import type { MenuItem } from '../../components/ModulePage.vue'

/** Community build: no EE Observe menus (Monitor). */
export function tenantOpsObserveMenus(_t: (key: string) => string): MenuItem[] {
  return []
}
