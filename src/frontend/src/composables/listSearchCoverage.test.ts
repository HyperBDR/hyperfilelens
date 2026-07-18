import { parse as parseTemplate, NodeTypes, type ElementNode, type RootNode } from '@vue/compiler-dom'
import { parse as parseSfc } from '@vue/compiler-sfc'
import { readdirSync, readFileSync } from 'node:fs'
import { relative, resolve } from 'node:path'
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

describe('list search coverage', () => {
  it('makes every clearable hfl list search apply clear immediately', () => {
    const sourceRoot = resolve(process.cwd(), 'src')
    const missing: string[] = []

    for (const file of vueFiles(sourceRoot)) {
      const source = readFileSync(file, 'utf8')
      const { descriptor } = parseSfc(source, { filename: file })
      if (!descriptor.template) continue
      const template = parseTemplate(descriptor.template.content)

      const visit = (node: ElementNode) => {
        const isInput = ['el-input', 'elinput'].includes(node.tag.toLowerCase())
        const hasListSearchClass = node.props.some((prop) =>
          prop.type === NodeTypes.ATTRIBUTE &&
          prop.name === 'class' &&
          prop.value?.content.includes('hfl-list-search'),
        )
        const isClearable = node.props.some((prop) =>
          prop.type === NodeTypes.ATTRIBUTE && prop.name === 'clearable',
        )
        const handlesClear = node.props.some((prop) =>
          prop.type === NodeTypes.DIRECTIVE &&
          prop.name === 'on' &&
          prop.arg?.type === NodeTypes.SIMPLE_EXPRESSION &&
          prop.arg.content === 'clear',
        )

        if (isInput && hasListSearchClass && isClearable && !handlesClear) {
          missing.push(`${relative(sourceRoot, file)}:${node.loc.start.line}`)
        }
        node.children.filter(isElement).forEach(visit)
      }

      template.children.filter(isElement).forEach(visit)
    }

    expect(missing).toEqual([])
  })

  it.each([
    ['pages/node/Nodes.vue', '@change="handleSearchFieldChange"'],
    ['pages/node/Repositories.vue', '@change="handleSearchFieldChange"'],
    ['pages/node/Repositories.vue', '@change="handleRepositoryTaskSearchFieldChange"'],
    ['pages/protection/BackupSources.vue', '@change="handleSearchFieldChange"'],
    ['pages/ops/Tasks.vue', '@change="handleSearchFieldChange"'],
    ['pages/ops/Audit.vue', '@change="handleSearchFieldChange"'],
    ['pages/protection/components/FlowBackupSourceDetailDrawer.vue', '@change="handleSourceTaskSearchFieldChange"'],
  ])('handles prepend search field changes in %s', (relativePath, binding) => {
    const source = readFileSync(resolve(process.cwd(), 'src', relativePath), 'utf8')
    expect(source).toContain(binding)
  })
})
