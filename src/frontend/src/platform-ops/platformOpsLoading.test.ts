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
})
