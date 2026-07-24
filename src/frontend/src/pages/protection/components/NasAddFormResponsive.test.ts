import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('NAS add form responsive layout', () => {
  it('keeps each mount field intact and stacks them on narrow screens', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/protection/components/NasAddForm.vue'), 'utf8')
    const mobileRules = source.match(/@media \(max-width: 900px\) \{([\s\S]*)\n\}/)?.[1] || ''

    expect(source).not.toContain('display: contents')
    expect(mobileRules).toContain('grid-template-columns: minmax(0, 1fr)')
    expect(mobileRules).toContain('flex-wrap: nowrap')
    expect(mobileRules).toContain('min-width: 0')
    expect(mobileRules).not.toContain('flex-basis: 100%')
  })

  it('keeps protocol choices compact on phones without changing desktop cards', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/protection/components/NasAddForm.vue'), 'utf8')

    expect(source).toMatch(/\.add-nas-protocol-card__icon\s*{[^}]*display:\s*inline-flex;/s)
    expect(source).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.add-nas-protocol-grid\s*{[^}]*gap:\s*8px;/,
    )
    expect(source).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.add-nas-protocol-grid :deep\(\.add-nas-protocol-card\)\s*{[^}]*min-height:\s*52px;/,
    )
    expect(source).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.add-nas-protocol-card__icon\s*{[^}]*display:\s*none;/,
    )
  })
})
