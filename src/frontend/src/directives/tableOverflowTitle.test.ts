// @vitest-environment jsdom

import type { App, Directive } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { setupTableOverflowTitleDirective } from './tableOverflowTitle'

describe('tableOverflowTitle', () => {
  let directive: Directive<HTMLElement>
  let table: HTMLElement
  let cell: HTMLElement
  let content: HTMLElement
  let secondaryContent: HTMLElement

  beforeAll(() => {
    vi.useFakeTimers()
    setupTableOverflowTitleDirective({
      directive: (_name: string, registered: Directive) => {
        directive = registered as Directive<HTMLElement>
      },
    } as Pick<App, 'directive'> as App)

    table = document.createElement('div')
    table.className = 'el-table'
    cell = document.createElement('div')
    cell.className = 'el-table__cell'
    const cellBody = document.createElement('div')
    cellBody.className = 'cell'
    content = document.createElement('div')
    content.innerText = 'notification.channel.create'
    content.style.overflow = 'hidden'
    Object.defineProperties(content, {
      clientWidth: { configurable: true, value: 80 },
      scrollWidth: { configurable: true, value: 200 },
    })
    secondaryContent = document.createElement('div')
    secondaryContent.innerText = 'NOTIFICATION_CHANNEL'
    secondaryContent.style.overflow = 'hidden'
    Object.defineProperties(secondaryContent, {
      clientWidth: { configurable: true, value: 80 },
      scrollWidth: { configurable: true, value: 200 },
    })
    cellBody.appendChild(content)
    cellBody.appendChild(secondaryContent)
    cell.appendChild(cellBody)
    table.appendChild(cell)
    document.body.appendChild(table)
    directive.mounted?.(table, {} as never, {} as never, {} as never)
  })

  afterAll(() => {
    directive.unmounted?.(table, {} as never, {} as never, {} as never)
    document.querySelector('#hfl-table-overflow-tooltip')?.remove()
    table.remove()
    vi.useRealTimers()
  })

  it('shows every independently overflowing line and stays open while the tooltip is hovered', () => {
    content.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
    vi.advanceTimersByTime(300)

    const tooltip = document.querySelector<HTMLElement>('#hfl-table-overflow-tooltip')
    expect(tooltip?.textContent).toBe('notification.channel.create\nNOTIFICATION_CHANNEL')
    expect(tooltip?.style.display).toBe('block')

    const gap = document.createElement('div')
    document.body.appendChild(gap)
    content.dispatchEvent(new MouseEvent('mouseout', { bubbles: true, relatedTarget: gap }))
    tooltip?.dispatchEvent(new MouseEvent('mouseenter'))
    cell.dispatchEvent(new FocusEvent('focusout', { bubbles: true }))
    vi.advanceTimersByTime(200)

    expect(tooltip?.style.display).toBe('block')

    tooltip?.dispatchEvent(new MouseEvent('mouseleave', { relatedTarget: gap }))
    vi.advanceTimersByTime(150)
    expect(tooltip?.style.display).toBe('none')
    gap.remove()
  })

  it('shows only the line that is overflowing', () => {
    Object.defineProperty(content, 'scrollWidth', { configurable: true, value: 80 })
    content.dataset.tableOverflowTitle = 'explicit primary content'

    secondaryContent.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
    vi.advanceTimersByTime(300)

    const tooltip = document.querySelector<HTMLElement>('#hfl-table-overflow-tooltip')
    expect(tooltip?.textContent).toBe('NOTIFICATION_CHANNEL')

    Object.defineProperty(content, 'scrollWidth', { configurable: true, value: 200 })
    content.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
    expect(tooltip?.textContent).toBe('explicit primary content')
    delete content.dataset.tableOverflowTitle
  })

  it('shows the tooltip when content overflows by exactly one pixel', () => {
    Object.defineProperty(content, 'clientWidth', { configurable: true, value: 80 })
    Object.defineProperty(content, 'scrollWidth', { configurable: true, value: 81 })
    Object.defineProperty(secondaryContent, 'clientWidth', { configurable: true, value: 80 })
    Object.defineProperty(secondaryContent, 'scrollWidth', { configurable: true, value: 80 })

    content.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
    vi.advanceTimersByTime(300)

    const tooltip = document.querySelector<HTMLElement>('#hfl-table-overflow-tooltip')
    expect(tooltip?.textContent).toBe('notification.channel.create')
    expect(tooltip?.style.display).toBe('block')
  })

  it('detects subpixel overflow when DOM scroll dimensions round to the same integer', () => {
    Object.defineProperty(content, 'clientWidth', { configurable: true, value: 80 })
    Object.defineProperty(content, 'scrollWidth', { configurable: true, value: 80 })
    Object.defineProperty(secondaryContent, 'clientWidth', { configurable: true, value: 80 })
    Object.defineProperty(secondaryContent, 'scrollWidth', { configurable: true, value: 80 })
    vi.spyOn(content, 'getBoundingClientRect').mockReturnValue({
      left: 0,
      right: 80.25,
      top: 0,
      bottom: 22,
      width: 80.25,
      height: 22,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    })
    const selectNodeContents = vi.fn()
    vi.spyOn(document, 'createRange').mockReturnValue({
      selectNodeContents,
      getBoundingClientRect: () => ({
        left: 0,
        right: 80.5,
        top: 0,
        bottom: 22,
        width: 80.5,
        height: 22,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }),
    } as unknown as Range)

    content.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
    vi.advanceTimersByTime(300)

    const tooltip = document.querySelector<HTMLElement>('#hfl-table-overflow-tooltip')
    expect(selectNodeContents).toHaveBeenCalledWith(content)
    expect(tooltip?.textContent).toBe('notification.channel.create')
    expect(tooltip?.style.display).toBe('block')
  })

  it('allows the tooltip text to receive pointer input and be selected', () => {
    const styles = readFileSync(resolve(process.cwd(), 'src/styles/list-page-ui.css'), 'utf8')
    expect(styles).toMatch(/\.hfl-table-overflow-tooltip\s*{[^}]*pointer-events:\s*auto;/s)
    expect(styles).toMatch(/\.hfl-table-overflow-tooltip\s*{[^}]*user-select:\s*text;/s)
    expect(styles).toMatch(/\.hfl-table-overflow-tooltip\s*{[^}]*white-space:\s*pre-line;/s)
  })
})
