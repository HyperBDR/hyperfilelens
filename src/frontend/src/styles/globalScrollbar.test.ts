import { readdirSync, readFileSync } from 'node:fs'
import { relative, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function styleSourcesBelow(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) return styleSourcesBelow(path)
    return /\.(?:css|scss|vue)$/.test(path) ? [path] : []
  })
}

describe('global scrollbar styles', () => {
  it('keeps native scrollbar appearance centralized in index.css', () => {
    const sourceRoot = resolve(process.cwd(), 'src')
    const scrollbarDeclaration = /scrollbar-(?:width|color)\s*:|::-webkit-scrollbar/
    const localOverrides = styleSourcesBelow(sourceRoot)
      .filter((file) => file !== resolve(sourceRoot, 'index.css'))
      .filter((file) => scrollbarDeclaration.test(readFileSync(file, 'utf8')))
      .map((file) => relative(sourceRoot, file))
      .sort()

    expect(localOverrides).toEqual([])
  })
})
