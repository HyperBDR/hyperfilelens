// @vitest-environment jsdom

import type { App, Directive, VNode } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { setupTableColumnResizeDirective } from '../directives/tableColumnResize'

type ResizeDirectiveHooks = {
  mounted: (el: HTMLElement, binding?: unknown, vnode?: VNode) => void
  unmounted: (el: HTMLElement) => void
}

function resizeDirective() {
  let hooks: ResizeDirectiveHooks | null = null
  const app = {
    directive(name: string, directive: Directive) {
      if (name === 'table-column-resize') hooks = directive as ResizeDirectiveHooks
      return this
    },
  } as unknown as App

  setupTableColumnResizeDirective(app)
  if (!hooks) throw new Error('table-column-resize directive was not registered')
  return hooks
}

function setClientWidth(element: HTMLElement, width: number) {
  Object.defineProperty(element, 'clientWidth', { configurable: true, value: width })
}

function pointerEvent(type: string, clientX: number) {
  const event = new MouseEvent(type, { bubbles: true, button: 0, clientX })
  Object.defineProperty(event, 'pointerId', { value: 1 })
  return event
}

function createResizableTable(viewportWidth: number) {
  const el = document.createElement('div')
  el.className = 'el-table'
  el.dataset.prefix = 'el'
  el.innerHTML = `
    <div class="el-table__inner-wrapper">
      <div class="el-table__header-wrapper">
        <table>
          <colgroup>
            <col name="el-table_1_column_1" width="150" style="width: 150px">
            <col name="el-table_1_column_2" width="150" style="width: 150px">
          </colgroup>
          <thead><tr>
            <th class="el-table__cell el-table_1_column_1"><div class="cell">Name</div></th>
            <th class="el-table__cell el-table_1_column_2"><div class="cell">Task</div></th>
          </tr></thead>
        </table>
      </div>
      <div class="el-table__body-wrapper">
        <table class="el-table__body">
          <colgroup>
            <col name="el-table_1_column_1" width="150" style="width: 150px">
            <col name="el-table_1_column_2" width="150" style="width: 150px">
          </colgroup>
          <tbody><tr>
            <td class="el-table__cell el-table_1_column_1"><div class="cell el-tooltip" style="width: 149px">restore-record-with-a-long-name</div></td>
            <td class="el-table__cell el-table_1_column_2"><div class="cell el-tooltip" style="width: 149px">task-with-a-long-name</div></td>
          </tr></tbody>
        </table>
      </div>
      <div class="el-table__fixed-body-wrapper">
        <table class="el-table__body">
          <colgroup><col name="el-table_1_column_1" width="150" style="width: 150px"></colgroup>
          <tbody><tr>
            <td class="el-table__cell el-table_1_column_1"><div class="cell el-tooltip" style="width: 149px">fixed-restore-record</div></td>
          </tr></tbody>
        </table>
      </div>
    </div>
  `

  setClientWidth(el, viewportWidth)
  for (const selector of ['.el-table__inner-wrapper', '.el-table__header-wrapper', '.el-table__body-wrapper']) {
    setClientWidth(el.querySelector<HTMLElement>(selector)!, viewportWidth)
  }
  const headers = el.querySelectorAll<HTMLTableCellElement>('th')
  headers[0]!.getBoundingClientRect = () => ({
    bottom: 44,
    height: 44,
    left: 0,
    right: 150,
    top: 0,
    width: 150,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  })
  headers[1]!.getBoundingClientRect = () => ({
    bottom: 44,
    height: 44,
    left: 150,
    right: 300,
    top: 0,
    width: 150,
    x: 150,
    y: 0,
    toJSON: () => ({}),
  })
  document.body.appendChild(el)
  return el
}

function dragFirstColumn(el: HTMLElement, endX: number) {
  const header = el.querySelector<HTMLTableCellElement>('th.el-table_1_column_1')!
  header.dispatchEvent(pointerEvent('pointerdown', 149))
  document.dispatchEvent(pointerEvent('pointermove', endX))
  document.dispatchEvent(pointerEvent('pointerup', endX))
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('resizable table overflow cells', () => {
  it('clips shared name columns and renders an ellipsis at the current width', () => {
    const styles = readFileSync(resolve(process.cwd(), 'src/styles/list-page-ui.css'), 'utf8')
    const nodesPage = readFileSync(resolve(process.cwd(), 'src/pages/node/Nodes.vue'), 'utf8')

    expect(styles).toMatch(/\.hfl-table-name-link--full\s*{[^}]*width:\s*100%;[^}]*max-width:\s*100%;[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis;/s)
    expect(styles).toMatch(/td\.hfl-table-name-col > \.cell\s*{[^}]*min-width:\s*0;[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis;/s)
    expect(styles).not.toMatch(/\.el-table-fixed-column--left\.hfl-table-name-col > \.cell\s*{[^}]*overflow:\s*visible;/s)
    expect(nodesPage).toContain('class-name="hfl-table-name-col"')
    expect(nodesPage).not.toContain(":class-name=\"isProxyNodesPage ? 'hfl-table-name-col' : undefined\"")
  })

  it('keeps normal and fixed tooltip cells synchronized while widening and narrowing a column', () => {
    const directive = resizeDirective()
    const el = createResizableTable(300)
    directive.mounted(el)

    dragFirstColumn(el, 249)

    expect(Array.from(el.querySelectorAll<HTMLTableColElement>('col[name="el-table_1_column_1"]'))
      .map((col) => col.style.width)).toEqual(['250px', '250px', '250px'])
    expect(Array.from(el.querySelectorAll<HTMLElement>('td.el-table_1_column_1 > .cell.el-tooltip'))
      .map((cell) => cell.style.width)).toEqual(['249px', '249px'])
    expect(el.querySelector<HTMLElement>('td.el-table_1_column_2 > .cell.el-tooltip')!.style.width).toBe('149px')

    dragFirstColumn(el, -101)

    expect(Array.from(el.querySelectorAll<HTMLTableColElement>('col[name="el-table_1_column_1"]'))
      .map((col) => col.style.width)).toEqual(['64px', '64px', '64px'])
    expect(Array.from(el.querySelectorAll<HTMLElement>('td.el-table_1_column_1 > .cell.el-tooltip'))
      .map((cell) => cell.style.width)).toEqual(['63px', '63px'])

    directive.unmounted(el)
  })

  it('synchronizes the tooltip width of a column that fills newly available space', () => {
    const directive = resizeDirective()
    const el = createResizableTable(400)
    directive.mounted(el)

    dragFirstColumn(el, 99)

    expect(el.querySelector<HTMLTableColElement>('col[name="el-table_1_column_1"]')!.style.width).toBe('100px')
    expect(el.querySelector<HTMLElement>('td.el-table_1_column_1 > .cell.el-tooltip')!.style.width).toBe('99px')
    expect(el.querySelector<HTMLTableColElement>('col[name="el-table_1_column_2"]')!.style.width).toBe('300px')
    expect(el.querySelector<HTMLElement>('td.el-table_1_column_2 > .cell.el-tooltip')!.style.width).toBe('299px')

    directive.unmounted(el)
  })
})
