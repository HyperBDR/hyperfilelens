import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const userList = readFileSync(resolve(process.cwd(), 'src/platform-ops/pages/users/UserList.vue'), 'utf8')
const orgList = readFileSync(resolve(process.cwd(), 'src/platform-ops/pages/orgs/OrgList.vue'), 'utf8')
const platformStyles = readFileSync(resolve(process.cwd(), 'src/platform-ops/styles/platform-ops-ui.css'), 'utf8')
const englishLocale = readFileSync(resolve(process.cwd(), 'src/locales/en.ts'), 'utf8')

function loadFunction(source: string) {
  return source.match(/async function load\(\) \{[\s\S]*?\n\}/)?.[0] || ''
}

describe('Admin Account Management reliability', () => {
  it.each([
    ['users', userList, 'platform-users'],
    ['organizations', orgList, 'platform-organizations'],
  ])('keeps successful %s data when a list request is cancelled or fails', (_name, source, scope) => {
    const load = loadFunction(source)

    expect(source).toContain("import { usePageRequestScope }")
    expect(load).toContain(`pageRequests.nextSignal('${scope}')`)
    expect(load).toContain('pageRequests.isAbortError(error)')
    expect(load).toContain('pageRequests.isCurrentSignal')
    expect(load).not.toContain('rows.value = []')
    expect(load).not.toContain('pagination.count = 0')
  })

  it('uses the customer-account business action on Organizations', () => {
    expect(orgList).toContain("t('platformOps.orgs.createCustomerAccount')")
    expect(orgList).toContain("t('platformOps.orgs.createCustomerAccountHint')")
    expect(orgList).not.toContain("t('platformOps.users.create')")
  })

  it('names organization support actions as Customer Account Support Mode', () => {
    expect(englishLocale).toContain("enterSupport: 'Open Customer Account in Support Mode'")
    expect(englishLocale).toContain("exitSupport: 'Exit Customer Support Mode'")
    expect(englishLocale).not.toContain("Enter tenant (read-only)")
  })

  it('keeps the 1280px account tables within the Admin content width', () => {
    expect(userList).toContain('min-width="185"')
    expect(userList).toContain('min-width="165"')
    expect(userList).toContain('width="156"')
    expect(orgList).toContain('min-width="195"')
    expect(orgList).toContain('min-width="185"')
    expect(orgList).toContain('width="164"')
  })

  it('scopes fixed-right action-column protection to the Admin Console shell', () => {
    expect(platformStyles).toContain('.platform-ops-shell .hfl-list-table th.el-table-fixed-column--right')
    expect(platformStyles).toContain('.platform-ops-shell .hfl-list-table td.el-table-fixed-column--right')
    expect(platformStyles).toContain('tr.el-table__row--striped td.el-table-fixed-column--right')
    expect(platformStyles).toContain('tr:hover > td.el-table-fixed-column--right')
    expect(platformStyles).toContain('.el-table-fixed-column--right.is-first-column::before')
  })
})
