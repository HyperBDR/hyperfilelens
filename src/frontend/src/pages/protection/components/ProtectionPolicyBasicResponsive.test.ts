import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(
  resolve(process.cwd(), 'src/pages/protection/components/ProtectionPolicyEditorForm.vue'),
  'utf8',
)

describe('protection policy basic fields responsive layout', () => {
  it('stretches name controls on phones without changing the desktop grid', () => {
    expect(source).toMatch(
      /\.policy-basic-row\s*{[^}]*grid-template-columns:\s*minmax\(124px, 148px\) minmax\(0, 1fr\);/s,
    )
    expect(source).toMatch(
      /@media \(max-width: 640px\)[\s\S]*?\.policy-basic-row\s*{[^}]*grid-template-columns:\s*1fr;[^}]*justify-items:\s*stretch;/,
    )
    expect(source).toMatch(
      /@media \(max-width: 640px\)[\s\S]*?\.policy-basic-row__control\s*{[^}]*width:\s*100%;[^}]*justify-self:\s*stretch;/,
    )
    expect(source).toMatch(
      /@media \(max-width: 640px\)[\s\S]*?\.policy-basic-row__control--switch\s*{[^}]*width:\s*auto;[^}]*justify-self:\s*start;/,
    )
  })
})
