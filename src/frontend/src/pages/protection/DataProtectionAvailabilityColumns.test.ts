import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const page = readFileSync(resolve(process.cwd(), 'src/pages/protection/DataProtection.vue'), 'utf8')
const createWizard = readFileSync(resolve(process.cwd(), 'src/pages/protection/BackupCreateWizard.vue'), 'utf8')

function tableForStep(step: number) {
  const startMarker = `<div v-if="flowMainStep === ${step}"`
  const start = page.indexOf(startMarker)
  const end = page.indexOf('</el-table>', start)
  expect(start).toBeGreaterThan(-1)
  expect(end).toBeGreaterThan(start)
  return page.slice(start, end)
}

function expectOrdered(text: string, markers: string[]) {
  let cursor = -1
  for (const marker of markers) {
    const next = text.indexOf(marker, cursor + 1)
    expect(next, `expected ${marker} after ${markers[Math.max(0, markers.indexOf(marker) - 1)]}`).toBeGreaterThan(cursor)
    cursor = next
  }
}

describe('Backup Wizard availability columns', () => {
  it.each([0, 1])('places Status after Endpoint and Availability before Registered in step %i', (step) => {
    expectOrdered(tableForStep(step), [
      'colConnectionAddress',
      'colStatus',
      'colCpu',
      'colMemory',
      'colDiskCount',
      'colAvailability',
      'colRegistered',
    ])
  })

  it('funds the first two wider Status columns from CPU, Memory, and Disks', () => {
    const connectionWidth = Number(page.match(/connection:\s*(\d+),/)?.[1])
    const statusWidths = [0, 1].map(step =>
      Number(tableForStep(step).match(/colStatus'[\s\S]*?width="(\d+)"/)?.[1]),
    )
    const pickWidths = page.match(/const FLOW_PICK_TABLE_COL_MIN = \{[\s\S]*?\} as const/)?.[0] ?? ''
    const cpuWidth = Number(pickWidths.match(/cpu:\s*(\d+),/)?.[1])
    const memoryWidth = Number(pickWidths.match(/memory:\s*(\d+),/)?.[1])
    const diskWidth = Number(pickWidths.match(/diskCount:\s*(\d+),/)?.[1])

    expect(connectionWidth).toBe(118)
    expect(statusWidths).toEqual([168, 168])
    expect([cpuWidth, memoryWidth, diskWidth]).toEqual([79, 90, 87])
    expect(cpuWidth + memoryWidth + diskWidth + statusWidths[0]).toBe(424)
  })

  it('places Availability immediately after Restore Task in step 3', () => {
    const step3Table = tableForStep(2)

    expectOrdered(step3Table, [
      'flowBackupColRestoreTaskStatus',
      'colAvailability',
      'flowBackupColTargetRepo',
    ])
    expect(Number(step3Table.match(/colStatus'[\s\S]*?width="(\d+)"/)?.[1])).toBe(168)
    expect(page).toContain('const FLOW_START_BACKUP_TABLE_COL_MIN = {\n  connection: 220,\n  backupDirs: 260,\n  compression: 190,\n  targetRepo: 280,\n  binding: 210,\n}')
  })

  it('maps the API availability field into each wizard row', () => {
    expect(page).toContain("availability: item.availability === 'online' ? 'online' : 'offline'")
    expect(page).toContain('flowSourceAvailabilityLabel(row.availability)')
  })

  it('uses availability rather than lifecycle status for Backup Setup connectivity checks', () => {
    expect(createWizard).toContain("availability: item.availability === 'online' ? 'online' : 'offline'")
    expect(createWizard).toContain(".filter((row): row is NonNullable<ReturnType<typeof sourceRecord>> => row != null && row.availability !== 'online')")
    expect(createWizard).toContain("const availability = sourceRecord(sourceId)?.availability")
    expect(createWizard).toContain("page: 1, page_size: 500, availability: 'online'")
    expect(createWizard).not.toContain("item.status === 'online' || item.status === 'reconnecting' ? item.status : 'offline'")
  })

  it('labels the Create Backup Configuration availability column accurately', () => {
    expect(createWizard).toContain("labelSourceAvailability")
    expect(createWizard).toContain('sourceAvailabilityLabel(row.id)')
    expect(createWizard).toContain('sourceAvailabilityTagType(row.id)')
    expect(createWizard).not.toContain('sourceStatusLabel(row.id)')
  })
})
