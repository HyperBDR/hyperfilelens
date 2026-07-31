import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const mainSource = readFileSync(resolve(process.cwd(), 'src/main.ts'), 'utf8')
const autofillStyles = readFileSync(resolve(process.cwd(), 'src/styles/auth-autofill.css'), 'utf8')

describe('auth autofill styles', () => {
  it('loads the shared auth autofill stylesheet', () => {
    expect(mainSource).toContain("import './styles/auth-autofill.css'")
  })

  it('keeps autofilled credentials aligned with the dark auth controls', () => {
    expect(autofillStyles).toContain('.login-container, .register-container')
    expect(autofillStyles).toContain('input:-webkit-autofill')
    expect(autofillStyles).toContain('input:autofill')
    expect(autofillStyles).toContain('-webkit-text-fill-color: #fff')
    expect(autofillStyles).toContain('caret-color: #fff')
    expect(autofillStyles).toContain('box-shadow: 0 0 0 1000px #313131 inset')
  })
})
