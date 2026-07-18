import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/directory-tree.css'), 'utf8')

describe('shared directory refresh button styles', () => {
  it('reveals the action on node hover, keyboard focus, and while refreshing', () => {
    expect(styles).toMatch(/\.hfl-dir-tree-node__refresh\s*{[^}]*opacity:\s*0;[^}]*pointer-events:\s*none;/s)
    expect(styles).toContain('.hfl-dir-tree .el-tree-node__content:hover .hfl-dir-tree-node__refresh')
    expect(styles).toContain('.hfl-dir-tree-node__refresh:focus-visible')
    expect(styles).toContain('.hfl-dir-tree-node__refresh.is-refreshing')
  })

  it('spins the refresh icon while the node request is active', () => {
    expect(styles).toMatch(/\.hfl-dir-tree-node__refresh \.is-spinning\s*{[^}]*animation:\s*hfl-dir-tree-refresh-spin/s)
    expect(styles).toContain('@keyframes hfl-dir-tree-refresh-spin')
  })
})
