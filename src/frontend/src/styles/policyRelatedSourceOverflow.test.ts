import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const policiesPage = readFileSync(resolve(process.cwd(), 'src/pages/protection/Policies.vue'), 'utf8')

describe('policy related source overflow styles', () => {
  it('renders both source lines with independent ellipses', () => {
    expect(policiesPage).toMatch(
      /\.policy-related-source-cell__name,\s*\.policy-related-source-cell__type\s*{[^}]*min-width:\s*0;[^}]*max-width:\s*100%;[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis;[^}]*white-space:\s*nowrap;/s,
    )
  })
})
