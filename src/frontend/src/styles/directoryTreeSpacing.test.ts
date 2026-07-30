import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/directory-tree.css'), 'utf8')
const backupCreateWizard = readFileSync(resolve(process.cwd(), 'src/pages/protection/BackupCreateWizard.vue'), 'utf8')

describe('recovery directory tree spacing', () => {
  it('separates adjacent top-level restore path choices', () => {
    expect(backupCreateWizard).toContain('create-recovery-popover-tree hfl-dir-tree')
    expect(styles).toMatch(
      /\.create-recovery-popover-tree\s*>\s*\.el-tree-node\s*\+\s*\.el-tree-node\s*{[^}]*margin-top:\s*4px;/s,
    )
    expect(styles).not.toContain('.hfl-dir-tree > .el-tree-node + .el-tree-node')
  })
})
