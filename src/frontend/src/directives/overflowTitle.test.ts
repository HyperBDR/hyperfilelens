// @vitest-environment jsdom

import type { App, Directive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setupTableOverflowTitleDirective } from './tableOverflowTitle'

describe('overflowTitle', () => {
  let directive: Directive<HTMLElement, string>
  let target: HTMLElement

  beforeEach(() => {
    vi.useFakeTimers()
    setupTableOverflowTitleDirective({
      directive: (name: string, registered: Directive) => {
        if (name === 'overflow-title') {
          directive = registered as Directive<HTMLElement, string>
        }
      },
    } as Pick<App, 'directive'> as App)

    target = document.createElement('span')
    target.innerText = 'host-01'
    Object.defineProperties(target, {
      clientWidth: { configurable: true, value: 80 },
      scrollWidth: { configurable: true, value: 120 },
      clientHeight: { configurable: true, value: 20 },
      scrollHeight: { configurable: true, value: 20 },
    })
    document.body.appendChild(target)
  })

  afterEach(() => {
    directive.unmounted?.(target, {} as never, {} as never, {} as never)
    target.remove()
    document.querySelector('#hfl-table-overflow-tooltip')?.remove()
    vi.useRealTimers()
  })

  it('uses the shared table tooltip only when content is truncated', () => {
    directive.mounted?.(
      target,
      { value: 'host-01 · 172.18.0.4 · Linux' } as never,
      {} as never,
      {} as never,
    )
    target.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
    vi.advanceTimersByTime(300)

    const tooltip = document.querySelector<HTMLElement>('#hfl-table-overflow-tooltip')
    expect(tooltip?.textContent).toBe('host-01 · 172.18.0.4 · Linux')
    expect(tooltip?.style.display).toBe('block')

    Object.defineProperty(target, 'scrollWidth', { configurable: true, value: 80 })
    target.dispatchEvent(new MouseEvent('mouseout', { bubbles: true }))
    vi.advanceTimersByTime(150)
    target.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
    vi.advanceTimersByTime(300)

    expect(tooltip?.style.display).toBe('none')
  })
})
