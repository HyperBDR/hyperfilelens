import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const listPages = [
  'pages/node/Nodes.vue',
  'pages/node/Repositories.vue',
  'pages/protection/BackupSources.vue',
  'pages/protection/Policies.vue',
]

describe('list search inputs', () => {
  it.each(listPages)('runs immediately when Enter is pressed in %s', (relativePath) => {
    const source = readFileSync(resolve(process.cwd(), 'src', relativePath), 'utf8')
    const searchInput = source.match(/<ElInput[\s\S]*?class="hfl-list-search hfl-list-search-group"[\s\S]*?>/)?.[0] || ''

    expect(searchInput).toContain('@keyup.enter="runFilterSearch"')
    expect(searchInput).not.toContain('@search=')
  })
})
