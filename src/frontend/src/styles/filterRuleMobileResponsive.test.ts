import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/fullscreen-form-shell.css'), 'utf8')

describe('file filter mobile responsive layout', () => {
  it('keeps desktop controls unchanged and applies compact phone-only overrides', () => {
    expect(styles).toMatch(/\.filter-custom-rule-row__remove\s*{[^}]*width:\s*36px;[^}]*height:\s*36px;/s)
    expect(styles).toMatch(/\.filter-custom-rule-add--row\s*{[^}]*width:\s*70%;/s)
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.policy-editor-fullscreen \.filter-rule-form \.filter-custom-rule-row\s*{[^}]*flex-wrap:\s*nowrap;/,
    )
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.filter-custom-rule-row__remove\s*{[^}]*width:\s*40px;[^}]*height:\s*40px;/,
    )
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.filter-custom-rule-add--row\s*{[^}]*width:\s*100%;/,
    )
  })

  it('reduces nested density and keeps the mode switch beside the title on phones', () => {
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.filter-rule-form > \.fullscreen-form-card\s*{[^}]*padding-right:\s*16px;[^}]*padding-left:\s*16px;/,
    )
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.filter-custom-head\s*{[^}]*display:\s*grid;[^}]*grid-template-columns:\s*minmax\(0, 1fr\) auto;/,
    )
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.filter-rule-group__notice\s*{[^}]*border:\s*0;[^}]*background:\s*transparent;/,
    )
  })

  it('keeps touch targets large while reducing their visible weight', () => {
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.filter-rule-guide-button,[\s\S]*?\.filter-custom-rule-text-toggle\s*{[^}]*border-color:\s*transparent;[^}]*background:\s*transparent;/,
    )
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.filter-custom-rule-row__pattern\.el-input\s*{[^}]*--el-input-height:\s*40px;[^}]*height:\s*44px;/,
    )
    expect(styles).toMatch(
      /@media \(max-width: 767\.98px\)[\s\S]*?\.filter-custom-rule-row__remove::after\s*{[^}]*inset:\s*-2px;/,
    )
  })
})
