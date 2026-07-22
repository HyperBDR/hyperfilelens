import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/list-page-ui.css'), 'utf8')

describe('responsive list toolbar controls', () => {
  it('keeps nested search field selects at their configured width', () => {
    expect(styles).toContain('.hfl-list-search-group .el-input-group__prepend .el-select')
    expect(styles).not.toMatch(/\.hfl-list-toolbar \.el-select\s*,/)
    expect(styles).toContain('.hfl-list-toolbar > .el-select,')
    expect(styles).toContain('.hfl-list-toolbar__right > .el-select,')
  })
})
