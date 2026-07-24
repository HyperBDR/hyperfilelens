import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(process.cwd(), 'src/pages/node/AddNasRepository.vue'), 'utf8')

describe('NAS repository responsive layout', () => {
  it('compacts protocol choices only within the mobile breakpoint', () => {
    expect(source).toMatch(/\.add-nas-protocol-grid\s*{[^}]*grid-template-columns:\s*repeat\(2,/s)
    expect(source).toMatch(/\.add-nas-protocol-card__icon\s*{[^}]*display:\s*inline-flex;/s)
    expect(source).toMatch(
      /@media \(max-width: 768px\)[\s\S]*?\.resource-add-fullscreen \.add-nas-protocol-grid\s*{[^}]*grid-template-columns:\s*repeat\(2,[^}]*gap:\s*8px;/,
    )
    expect(source).toMatch(
      /@media \(max-width: 768px\)[\s\S]*?\.resource-add-fullscreen \.add-nas-protocol-card\s*{[^}]*min-height:\s*52px;/,
    )
    expect(source).toMatch(
      /@media \(max-width: 768px\)[\s\S]*?\.resource-add-fullscreen \.add-nas-protocol-card__icon\s*{[^}]*display:\s*none;/,
    )
  })
})
