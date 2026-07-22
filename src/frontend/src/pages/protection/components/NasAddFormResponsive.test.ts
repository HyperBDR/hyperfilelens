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
})
