import { CloudCog } from 'lucide-vue-next'
import { describe, expect, it, vi } from 'vitest'
import { usePlatformOpsSideNav } from './usePlatformOpsSideNav'

const mocks = vi.hoisted(() => ({
  t: vi.fn((key: string) => key),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: mocks.t }),
}))

describe('usePlatformOpsSideNav', () => {
  it('keeps SourceLens administration under Platform Integrations only', () => {
    const menus = usePlatformOpsSideNav().value
    const items = menus.flatMap((item) => item.children || [item])

    expect(
      items.some((item) => item.to === '/platform-ops/engine/data-connections'),
    ).toBe(false)
    expect(
      items.filter((item) => item.to === '/platform-ops/platform/integrations'),
    ).toHaveLength(1)
  })

  it('places Storage Providers under the non-navigable Storage group', () => {
    const menus = usePlatformOpsSideNav().value
    const storageGroup = menus.find(
      (item) => item.label === 'platformOps.nav.groupStorage',
    )

    expect(storageGroup).toBeDefined()
    expect(storageGroup?.to).toBeUndefined()
    expect(storageGroup?.children).toHaveLength(1)
    expect(storageGroup?.children?.[0]).toMatchObject({
      label: 'platformOps.nav.storageProviders',
      to: '/platform-ops/storage-providers',
      icon: CloudCog,
      pageTitle: 'platformOps.storageProviders.title',
    })
    expect(
      menus.some((item) => item.to === '/platform-ops/storage-providers'),
    ).toBe(false)
  })
})
