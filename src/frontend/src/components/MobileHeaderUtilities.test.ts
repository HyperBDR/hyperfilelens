import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), 'utf8')
}

const appShell = source('src/app/layout/AppShell.vue')
const topNav = source('src/app/layout/TopNav.vue')
const drawer = source('src/components/MobileNavigationDrawer.vue')
const userMenu = source('src/components/NavUserMenu.vue')
const dropdownStyles = source('src/styles/nav-dropdown-panel.css')
const locale = source('src/locales/en.ts')

describe('mobile header utilities', () => {
  it('shares deploy profile and locale state from the app shell', () => {
    expect(appShell).toContain('async function refreshHeaderProfile()')
    expect(appShell).toContain(':admin-console-href="adminConsoleHref"')
    expect(appShell).toContain(':can-switch-locale="canSwitchLocale"')
    expect(appShell).toContain('@toggle-locale="toggleLocale"')
    expect(topNav).not.toContain('fetchDeployProfile')
  })

  it('keeps hidden desktop utilities reachable from mobile surfaces', () => {
    expect(drawer).toContain('<OrgSwitcher variant="mobile" />')
    expect(drawer).toContain('target="_blank"')
    expect(drawer).toContain("$t('nav.platformOps')")
    expect(drawer).toContain("$t('nav.switchLanguage', { language: nextLocaleLabel })")
    expect(userMenu).toContain("t('nav.timezoneLabel')")
    expect(userMenu).toContain('{{ timezoneOffsetDisplay }}')
    expect(userMenu).toMatch(
      /@media \(max-width: 1023\.98px\)[\s\S]*?\.nav-user-timezone\s*{[\s\S]*?display:\s*flex/,
    )
    expect(locale).toContain("timezoneLabel: 'Time Zone'")
    expect(locale).toContain("switchLanguage: 'Switch to {language}'")
  })

  it('keeps mobile triggers and popovers within narrow viewports', () => {
    expect(userMenu).toMatch(
      /@media \(max-width: 1023\.98px\)[\s\S]*?\.nav-user-trigger\s*{[\s\S]*?min-height:\s*44px/,
    )
    expect(dropdownStyles).toMatch(
      /\.nav-dropdown-popover\.el-popper\s*{[\s\S]*?max-width:\s*calc\(100vw - 24px\)/,
    )
  })
})
