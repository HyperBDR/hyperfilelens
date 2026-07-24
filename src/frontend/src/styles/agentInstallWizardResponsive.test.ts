import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/agent-install-wizard.css'), 'utf8')

describe('agent install wizard responsive layout', () => {
  it('compacts source host OS choices only on phones', () => {
    expect(styles).toMatch(/\.agent-install-wizard--source-host \.os-icon-card\s*{[^}]*min-height:\s*124px;/s)
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.agent-install-wizard--source-host \.os-icon-card\s*{[^}]*min-height:\s*76px;[^}]*padding:\s*12px 48px 12px 66px;/,
    )
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.os-icon-card__icon-wrap\s*{[^}]*position:\s*absolute;[^}]*left:\s*14px;/,
    )
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.os-icon-card__check\s*{[^}]*position:\s*absolute;[^}]*right:\s*14px;/,
    )
  })
})
