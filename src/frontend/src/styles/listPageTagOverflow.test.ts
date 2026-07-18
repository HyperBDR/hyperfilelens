import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/list-page-ui.css'), 'utf8')

describe('list table tag overflow styles', () => {
  it('clips tag text horizontally without clipping glyph descenders', () => {
    expect(styles).toMatch(/\.el-tag__content\s*{[^}]*line-height:\s*16px;[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis;[^}]*white-space:\s*nowrap;/s)
    expect(styles).not.toMatch(/\.cell \.el-tag\s*{[^}]*top:\s*-1px;/s)
  })
})
