import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const listPages = [
  'pages/users/UserList.vue',
  'pages/orgs/OrgList.vue',
  'pages/monitoring/MonitoringNodes.vue',
  'pages/monitoring/MonitoringTasks.vue',
  'pages/platform/PlatformAgentReleases.vue',
]

describe('Admin Console list loading', () => {
  it.each(listPages)('uses the loading directive for tables in %s', (relativePath) => {
    const source = readFileSync(resolve(process.cwd(), 'src/platform-ops', relativePath), 'utf8')
    const tableTags = source.match(/<el-table\b[\s\S]*?>/g) || []

    expect(tableTags.length).toBeGreaterThan(0)
    expect(tableTags.some((tag) => /\bv-loading="busy"/.test(tag))).toBe(true)
    expect(tableTags.every((tag) => !/\s:loading=/.test(tag))).toBe(true)
  })

  it('keeps shared table empty content centered without a second horizontal offset', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/styles/element-plus-table.css'), 'utf8')
    const emptyTextRule = source.match(/\.el-table__empty-text\s*\{([^}]*)\}/)?.[1] || ''

    expect(emptyTextRule).toContain('width: 100%')
    expect(emptyTextRule).toContain('align-items: center')
    expect(emptyTextRule).toContain('justify-content: center')
    expect(emptyTextRule).toContain('text-align: center')
    expect(emptyTextRule).toContain('transform: none')
    expect(emptyTextRule).not.toContain('translateX')
  })
})
