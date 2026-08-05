import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function source(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), 'src', relativePath), 'utf8')
}

function ordered(text: string, markers: string[]): boolean {
  let cursor = -1
  for (const marker of markers) {
    cursor = text.indexOf(marker, cursor + 1)
    if (cursor < 0) return false
  }
  return true
}

function declaredTableWidth(text: string): number {
  return [...text.matchAll(/\b(?:min-)?width="(\d+)"/g)]
    .reduce((total, match) => total + Number(match[1]), 0)
}

describe('Production Sites availability presentation', () => {
  const list = source('pages/protection/BackupSources.vue')
  const proxyList = source('pages/node/Nodes.vue')
  const hostStart = list.indexOf(':data="pagedHostAgents"')
  const nasStart = list.indexOf(':data="nasRows"')
  const proxyStart = proxyList.indexOf('v-table-column-resize="isProxyNodesPage')
  const hostTable = list.slice(hostStart, list.indexOf('</el-table>', hostStart))
  const nasTable = list.slice(nasStart, list.indexOf('</el-table>', nasStart))
  const proxyTable = proxyList.slice(proxyStart, proxyList.indexOf('<template v-else>', proxyStart))

  it('keeps host lifecycle status separate and places availability before version', () => {
    expect(ordered(hostTable, [
      'colName',
      'colStatus',
      'colHostIp',
      'colCapacity',
      'colAvailability',
      'colVersion',
      'colRegistered',
    ])).toBe(true)
  })

  it('places NAS lifecycle status immediately after name and keeps availability before registration', () => {
    expect(ordered(nasTable, [
      'colName',
      'colStatus',
      'colProtocol',
      'colAvailability',
      'colRegistered',
    ])).toBe(true)
  })

  it('does not repeat proxy availability in the NAS status column', () => {
    expect(nasTable).not.toContain('proxyStatus')
  })

  it('places Proxy Hosts status after name and availability before version', () => {
    expect(ordered(proxyTable, [
      'colName',
      'colStatus',
      'colHostIp',
      'colCapacity',
      'colAvailability',
      'colVersion',
      'colRegistered',
    ])).toBe(true)
  })

  it('keeps both desktop table width budgets below 1400 pixels', () => {
    expect(declaredTableWidth(hostTable)).toBeLessThanOrEqual(1400)
    expect(declaredTableWidth(nasTable)).toBeLessThanOrEqual(1400)
  })

  it.each([
    'components/NodeBasicInfoPanel.vue',
    'pages/protection/components/NasSourceDetailDrawer.vue',
  ])('shows availability and its observation time in %s', (relativePath) => {
    const detail = source(relativePath)
    expect(detail).toContain('colAvailability')
    expect(detail).toContain('fieldAvailabilityUpdatedAt')
    expect(detail).toContain('availability_updated_at')
  })
})
