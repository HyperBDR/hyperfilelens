import { parse as parseTemplate, NodeTypes, type ElementNode, type RootNode } from '@vue/compiler-dom'
import { parse as parseSfc } from '@vue/compiler-sfc'
import { readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function vueFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) return vueFiles(path)
    return path.endsWith('.vue') ? [path] : []
  })
}

function isElement(node: RootNode['children'][number]): node is ElementNode {
  return node.type === NodeTypes.ELEMENT
}

function hasSharedNameColumn(node: ElementNode): boolean {
  const tag = node.tag.toLowerCase()
  if (tag === 'el-table-column' || tag === 'eltablecolumn') {
    return node.props.some((prop) => {
      if (prop.type === NodeTypes.ATTRIBUTE) {
        return prop.name === 'class-name' && prop.value?.content.includes('hfl-table-name-col')
      }
      return (
        prop.name === 'bind' &&
        prop.arg?.type === NodeTypes.SIMPLE_EXPRESSION &&
        prop.arg.content === 'class-name' &&
        prop.exp?.type === NodeTypes.SIMPLE_EXPRESSION &&
        prop.exp.content.includes('hfl-table-name-col')
      )
    })
  }
  return node.children.filter(isElement).some(hasSharedNameColumn)
}

describe('table overflow tooltip coverage', () => {
  it('installs the shared directive on every table with a shared name column', () => {
    const missing: string[] = []

    for (const file of vueFiles(resolve(process.cwd(), 'src'))) {
      const source = readFileSync(file, 'utf8')
      const { descriptor } = parseSfc(source, { filename: file })
      if (!descriptor.template) continue

      const template = parseTemplate(descriptor.template.content)
      const visit = (node: ElementNode) => {
        const tag = node.tag.toLowerCase()
        const isTable = tag === 'el-table' || tag === 'eltable'
        const hasDirective = node.props.some(
          (prop) => prop.type === NodeTypes.DIRECTIVE && prop.name === 'table-overflow-title',
        )
        if (isTable && hasSharedNameColumn(node) && !hasDirective) {
          missing.push(`${file}:${node.loc.start.line}`)
        }
        node.children.filter(isElement).forEach(visit)
      }

      template.children.filter(isElement).forEach(visit)
    }

    expect(missing).toEqual([])
  })

  it('does not combine the shared directive with Element Plus overflow tooltips', () => {
    const duplicates: string[] = []

    for (const file of vueFiles(resolve(process.cwd(), 'src'))) {
      const source = readFileSync(file, 'utf8')
      const { descriptor } = parseSfc(source, { filename: file })
      if (!descriptor.template) continue

      const template = parseTemplate(descriptor.template.content)
      const visit = (node: ElementNode, sharedTable = false) => {
        const tag = node.tag.toLowerCase()
        const isTable = tag === 'el-table' || tag === 'eltable'
        const isColumn = tag === 'el-table-column' || tag === 'eltablecolumn'
        let insideSharedTable = sharedTable

        if (isTable) {
          insideSharedTable = node.props.some((prop) =>
            (prop.type === NodeTypes.ATTRIBUTE &&
              prop.name === 'class' &&
              prop.value?.content.includes('hfl-list-table')) ||
            (prop.type === NodeTypes.DIRECTIVE && prop.name === 'table-overflow-title'),
          )
        }

        if (
          isColumn &&
          insideSharedTable &&
          node.props.some((prop) => prop.type === NodeTypes.ATTRIBUTE && prop.name === 'show-overflow-tooltip')
        ) {
          duplicates.push(`${file}:${node.loc.start.line}`)
        }

        node.children.filter(isElement).forEach((child) => visit(child, insideSharedTable))
      }

      template.children.filter(isElement).forEach((node) => visit(node))
    }

    expect(duplicates).toEqual([])
  })

  it.each([
    'components/BackupSourceResetDialogBody.vue',
    'components/BackupSourceUnregisterDialogBody.vue',
    'components/ProtectionStopConfirmDialog.vue',
  ])('installs the shared directive in %s', (relativePath) => {
    const source = readFileSync(resolve(process.cwd(), 'src', relativePath), 'utf8')
    expect(source).toContain('v-table-overflow-title')
  })
})
