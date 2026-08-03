import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const primaryNavSource = readFileSync(
  resolve(process.cwd(), 'src/composables/useAppPrimaryNav.ts'),
  'utf8',
)
const topNavSource = readFileSync(resolve(process.cwd(), 'src/app/layout/TopNav.vue'), 'utf8')
const mobileNavSource = readFileSync(
  resolve(process.cwd(), 'src/components/MobileNavigationDrawer.vue'),
  'utf8',
)

describe('primary navigation icons', () => {
  it('defines one shared Lucide icon for every primary destination', () => {
    expect(primaryNavSource).toContain("{ to: '/', label: t('nav.overview'), icon: LayoutDashboard }")
    expect(primaryNavSource).toContain(
      "{ to: '/protection', label: t('nav.protection'), icon: ShieldCheck }",
    )
    expect(primaryNavSource).toContain(
      "{ to: '/insight', label: t('nav.insight'), icon: ChartNoAxesCombined }",
    )
    expect(primaryNavSource).toContain("{ to: '/node', label: t('nav.node'), icon: Settings }")
    expect(primaryNavSource).toContain("{ to: '/ops', label: t('nav.ops'), icon: Activity }")
  })

  it('renders decorative icons alongside labels in desktop and mobile navigation', () => {
    expect(topNavSource).toMatch(
      /:is="item\.icon"[\s\S]*?class="nav-item__icon"[\s\S]*?:size="16"[\s\S]*?aria-hidden="true"/,
    )
    expect(topNavSource).toContain('<span>{{ item.label }}</span>')

    expect(mobileNavSource).toMatch(
      /:is="item\.icon"[\s\S]*?:size="17"[\s\S]*?:stroke-width="2"[\s\S]*?aria-hidden="true"/,
    )
    expect(mobileNavSource).toContain('<span>{{ item.label }}</span>')
  })

  it('compacts icons and timezone text at constrained desktop widths', () => {
    expect(topNavSource).toMatch(
      /@media \(min-width: 1024px\) and \(max-width: 1279\.98px\)[\s\S]*?\.nav-item__icon\s*{[\s\S]*?display:\s*none/,
    )
    expect(topNavSource).toMatch(
      /@media \(min-width: 1024px\) and \(max-width: 1439\.98px\)[\s\S]*?\.timezone-display__label\s*{[\s\S]*?display:\s*none/,
    )
    expect(topNavSource).toContain('class="timezone-display__label"')
    expect(topNavSource).toMatch(
      /@media \(max-width: 1023\.98px\)[\s\S]*?\.nav-menu,[\s\S]*?display:\s*none/,
    )
  })
})
