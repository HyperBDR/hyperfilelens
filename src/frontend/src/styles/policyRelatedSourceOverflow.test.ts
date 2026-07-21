import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const policiesPage = readFileSync(resolve(process.cwd(), 'src/pages/protection/Policies.vue'), 'utf8')

describe('policy related source overflow styles', () => {
  it('truncates long source names without collapsing the metadata row', () => {
    expect(policiesPage).toMatch(
      /\.policy-related-source-cell__name\s*{[^}]*min-width:\s*0;[^}]*max-width:\s*100%;[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis;[^}]*white-space:\s*nowrap;/s,
    )
    expect(policiesPage).toMatch(
      /\.policy-related-source-cell__meta\s*{[^}]*display:\s*flex;[^}]*min-width:\s*0;[^}]*align-items:\s*center;/s,
    )
  })
})
