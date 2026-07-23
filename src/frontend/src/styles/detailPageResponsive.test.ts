import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/detail-page-ui.css'), 'utf8')

describe('responsive detail rows', () => {
  it('uses the same label width for regular and full rows in single-column layouts', () => {
    const mobileStyles = styles.slice(styles.indexOf('@media (max-width: 860px)'))

    expect(mobileStyles).toContain('.hfl-detail-row--full,')
    expect(mobileStyles).toContain('.detail-page-row--full {')
    expect(mobileStyles).toContain('grid-template-columns: minmax(112px, 34%) minmax(0, 1fr)')
  })
})
