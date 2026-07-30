import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const styles = readFileSync(resolve(process.cwd(), 'src/styles/directory-tree.css'), 'utf8')
const newCopilotChat = readFileSync(resolve(process.cwd(), 'src/pages/insight/NewCopilotChat.vue'), 'utf8')
const knowledgeSourceForm = readFileSync(resolve(process.cwd(), 'src/pages/insight/KnowledgeSourceFormPage.vue'), 'utf8')

const directoryIconClass = 'class="hfl-dir-tree-node__icon hfl-dir-tree-node__icon--dir"'
const fileIconClass = 'class="hfl-dir-tree-node__icon hfl-dir-tree-node__icon--file"'

describe('shared directory tree icon types', () => {
  it('uses the established folder and file colors', () => {
    expect(styles).toMatch(/\.hfl-dir-tree-node__icon--dir\s*{[^}]*color:\s*#d97706;/s)
    expect(styles).toMatch(/\.hfl-dir-tree-node__icon--file\s*{[^}]*color:\s*#2563eb;/s)
  })

  it.each([
    ['New Chat', newCopilotChat],
    ['Knowledge Source form', knowledgeSourceForm],
  ])('distinguishes folders and files in the %s backup scope picker', (_name, source) => {
    expect(source).toContain(directoryIconClass)
    expect(source).toContain(fileIconClass)
  })
})
