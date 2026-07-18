import type { App, VNode } from 'vue'

type ResizeTarget = {
  th: HTMLTableCellElement
  table: ElementPlusTableLike | null
  column: ElementPlusTableColumn | null
  columnId: string | null
  index: number
}

type DragState = {
  target: ResizeTarget
  pointerId: number
  startX: number
  startWidth: number
  previousUserSelect: string
  previousCursor: string
}

type ResizeState = {
  drag: DragState | null
  hotTh: HTMLTableCellElement | null
  proxy: HTMLDivElement
  onPointerMove: (event: PointerEvent) => void
  onPointerDown: (event: PointerEvent) => void
  onPointerLeave: () => void
  onDocumentPointerMove: (event: PointerEvent) => void
  onDocumentPointerUp: () => void
  onDocumentPointerCancel: () => void
  onLostPointerCapture: () => void
  onWindowBlur: () => void
}

type ElementPlusTableColumn = {
  id?: string
  width?: number | string | null
  realWidth?: number | null
  children?: ElementPlusTableColumn[]
}

type ElementPlusStore = {
  states?: {
    columns?: { value?: ElementPlusTableColumn[] }
    _columns?: { value?: ElementPlusTableColumn[] }
    originColumns?: { value?: ElementPlusTableColumn[] }
  }
  scheduleLayout?: (needUpdateColumns?: boolean, immediate?: boolean) => void
}

type ElementPlusTableLike = {
  store?: ElementPlusStore
  state?: {
    doLayout?: () => void
  }
  refs?: {
    headerWrapper?: HTMLElement
    footerWrapper?: HTMLElement
    scrollBarRef?: {
      wrapRef?: HTMLElement
      update?: () => void
    }
  }
  doLayout?: () => void
  setScrollLeft?: (value: number) => void
  proxy?: ElementPlusTableLike | null
  exposed?: ElementPlusTableLike | null
  parent?: ElementPlusTableLike | null
}

const MIN_COLUMN_WIDTH = 64
const RESIZE_HOT_ZONE_PX = 12
const COLUMN_ID_PATTERN = /^el-table_\d+_column_\d+$/
const RESIZE_HOT_CLASS = 'hfl-column-resize-hot'
const COLUMN_RESIZED_EVENT = 'hfl-table-column-resized'
const ELEMENT_PLUS_TOOLTIP_WIDTH_OFFSET = 1

const stateByElement = new WeakMap<HTMLElement, ResizeState>()
const layoutFrameByElement = new WeakMap<HTMLElement, number>()
const tableByElement = new WeakMap<HTMLElement, ElementPlusTableLike>()

function isCurrentTableElement(el: HTMLElement, node: Element | null) {
  let current = node
  while (current) {
    if (current instanceof HTMLElement && stateByElement.has(current)) return current === el
    current = current.parentElement
  }
  return false
}

function findHeaderCell(el: HTMLElement, event: PointerEvent): HTMLTableCellElement | null {
  const target = event.target instanceof Element ? event.target.closest<HTMLTableCellElement>('th.el-table__cell') : null
  if (!target || !isCurrentTableElement(el, target)) return null
  if (target.classList.contains('el-table-column--selection')) return null
  if (target.classList.contains('el-table__expand-column')) return null
  if (target.colSpan !== 1) return null
  return target
}

function isInResizeZone(th: HTMLTableCellElement, event: PointerEvent) {
  const rect = th.getBoundingClientRect()
  return rect.right - event.clientX >= 0 && rect.right - event.clientX <= RESIZE_HOT_ZONE_PX
}

function columnIdForCell(th: HTMLTableCellElement) {
  return Array.from(th.classList).find((className) => COLUMN_ID_PATTERN.test(className)) ?? null
}

function columnIndexForCell(th: HTMLTableCellElement) {
  return Array.from(th.parentElement?.children ?? []).indexOf(th)
}

function hasTableStore(candidate: ElementPlusTableLike | null | undefined) {
  const columns = candidate?.store?.states?.columns
  return Boolean(columns && 'value' in columns ? columns.value?.length : columns)
}

function columnForTarget(
  table: ElementPlusTableLike | null,
  columnId: string | null,
  index: number,
): ElementPlusTableColumn | null {
  const columns = tableColumns(table)
  if (!columns.length) return null
  if (columnId) {
    return columns.find((item) => item.id === columnId) ?? null
  }
  const leafColumns = columns.filter((item) => !item.children?.length)
  return leafColumns[index] ?? columns[index] ?? null
}

function findResizeTarget(el: HTMLElement, event: PointerEvent): ResizeTarget | null {
  const th = findHeaderCell(el, event)
  if (!th || !isInResizeZone(th, event)) return null
  const index = columnIndexForCell(th)
  if (index < 0) return null
  const columnId = columnIdForCell(th)
  const resolvedTable = tableInstanceForElement(el)
  const column = columnForTarget(resolvedTable, columnId, index)
  const table = column ? resolvedTable : null

  return {
    th,
    table,
    column,
    columnId,
    index,
  }
}

function normalizeWidth(value: unknown) {
  const width = Number(value)
  return Number.isFinite(width) ? Math.max(MIN_COLUMN_WIDTH, Math.round(width)) : 0
}

function tableCols(el: HTMLElement): HTMLTableColElement[] {
  return Array.from(el.querySelectorAll<HTMLTableColElement>('colgroup col')).filter((col) => isCurrentTableElement(el, col))
}

function headerCells(el: HTMLElement): HTMLTableCellElement[] {
  return Array.from(el.querySelectorAll<HTMLTableCellElement>('.el-table__header-wrapper th.el-table__cell'))
    .filter((th) => isCurrentTableElement(el, th))
    .filter((th) => th.colSpan === 1)
}

function isDataHeaderCell(th: HTMLTableCellElement) {
  return !th.classList.contains('el-table-column--selection') &&
    !th.classList.contains('el-table__expand-column')
}

function targetCols(el: HTMLElement, target: ResizeTarget): HTMLTableColElement[] {
  if (target.columnId) {
    const cols = tableCols(el).filter((col) => col.getAttribute('name') === target.columnId)
    if (cols.length) return cols
  }

  return Array.from(el.querySelectorAll<HTMLTableColElement>('colgroup'))
    .filter((group) => isCurrentTableElement(el, group))
    .map((group) => Array.from(group.querySelectorAll<HTMLTableColElement>('col'))[target.index])
    .filter((col): col is HTMLTableColElement => Boolean(col))
}

function resolveTableInstance(instance: ElementPlusTableLike | null | undefined): ElementPlusTableLike | null {
  while (instance) {
    const candidates = [instance, instance.proxy, instance.exposed]
    const match = candidates.find((candidate) => hasTableStore(candidate))
    if (match) return match
    instance = instance.parent ?? null
  }
  return null
}

function tableInstanceForVNode(vnode: VNode | null | undefined) {
  return resolveTableInstance((vnode?.component ?? null) as ElementPlusTableLike | null)
}

function tableInstanceForElement(el: HTMLElement): ElementPlusTableLike | null {
  return (
    tableByElement.get(el) ??
    resolveTableInstance((el as HTMLElement & { __vueParentComponent?: ElementPlusTableLike | null }).__vueParentComponent)
  )
}

function flattenColumns(columns: ElementPlusTableColumn[] = []): ElementPlusTableColumn[] {
  return columns.flatMap((column) => [column, ...flattenColumns(column.children)])
}

function tableColumns(table: ElementPlusTableLike | null) {
  const states = table?.store?.states
  const columns = flattenColumns([
    ...(states?.columns?.value ?? []),
    ...(states?._columns?.value ?? []),
    ...(states?.originColumns?.value ?? []),
  ])
  return Array.from(new Set(columns))
}

function columnById(table: ElementPlusTableLike | null, columnId: string | null) {
  if (!columnId) return null
  return tableColumns(table).find((item) => item.id === columnId) ?? null
}

function currentWidth(el: HTMLElement, target: ResizeTarget) {
  if (target.column) {
    const columnWidth = normalizeWidth(target.column.realWidth ?? target.column.width)
    if (columnWidth) return columnWidth
  }

  const col = targetCols(el, target)[0]
  const rawColWidth = col?.getAttribute('width') ?? col?.style?.width ?? ''
  const colWidth = normalizeWidth(rawColWidth.replace('px', ''))
  if (colWidth) return colWidth
  return normalizeWidth(target.th.getBoundingClientRect().width)
}

function syncTableScrollPosition(table: ElementPlusTableLike) {
  const scrollLeft = table.refs?.scrollBarRef?.wrapRef?.scrollLeft ?? 0
  if (table.refs?.headerWrapper) table.refs.headerWrapper.scrollLeft = scrollLeft
  if (table.refs?.footerWrapper) table.refs.footerWrapper.scrollLeft = scrollLeft
  table.setScrollLeft?.(scrollLeft)
}

function queueTableLayout(el: HTMLElement, table: ElementPlusTableLike) {
  if (layoutFrameByElement.has(el)) return
  const frame = window.requestAnimationFrame(() => {
    layoutFrameByElement.delete(el)
    const latestTable = tableInstanceForElement(el) ?? table
    if (latestTable.store?.scheduleLayout) {
      latestTable.store.scheduleLayout(true, true)
    } else {
      latestTable.doLayout?.()
      latestTable.state?.doLayout?.()
    }
    latestTable.refs?.scrollBarRef?.update?.()
    window.requestAnimationFrame(() => {
      syncAllOverflowCellWidths(el)
      syncTableScrollPosition(latestTable)
    })
  })
  layoutFrameByElement.set(el, frame)
}

function tableViewportWidth(el: HTMLElement) {
  const bodyWrapper = el.querySelector<HTMLElement>('.el-table__body-wrapper')
  const headerWrapper = el.querySelector<HTMLElement>('.el-table__header-wrapper')
  const innerWrapper = el.querySelector<HTMLElement>('.el-table__inner-wrapper')
  return Math.floor(Math.max(
    el.clientWidth || 0,
    innerWrapper?.clientWidth || 0,
    headerWrapper?.clientWidth || 0,
    bodyWrapper?.clientWidth || 0,
  ))
}

function primaryColWidth(el: HTMLElement, columnId: string | null) {
  if (!columnId) return 0
  const col = tableCols(el).find((item) => item.getAttribute('name') === columnId)
  const raw = col?.getAttribute('width') ?? col?.style.width ?? ''
  return normalizeWidth(raw.replace('px', ''))
}

function syncOverflowCellWidth(el: HTMLElement, columnId: string | null, width: number) {
  if (!columnId) return
  const tooltipClass = `${el.dataset.prefix || 'el'}-tooltip`
  const contentWidth = Math.max(0, Math.round(width) - ELEMENT_PLUS_TOOLTIP_WIDTH_OFFSET)
  const cells = Array.from(el.querySelectorAll<HTMLElement>(`td.${columnId} > .cell.${tooltipClass}`))
    .filter((cell) => isCurrentTableElement(el, cell))

  for (const cell of cells) {
    cell.style.width = `${contentWidth}px`
  }
}

function syncAllOverflowCellWidths(el: HTMLElement) {
  for (const cell of uniqueHeaderCells(el)) {
    const columnId = columnIdForCell(cell)
    const width = primaryColWidth(el, columnId)
    if (width) syncOverflowCellWidth(el, columnId, width)
  }
}

function uniqueHeaderCells(el: HTMLElement) {
  const seen = new Set<string>()
  return headerCells(el).filter((cell) => {
    const columnId = columnIdForCell(cell)
    if (!columnId) return true
    if (seen.has(columnId)) return false
    seen.add(columnId)
    return true
  })
}

function setColumnWidth(el: HTMLElement, table: ElementPlusTableLike | null, columnId: string | null, width: number) {
  if (!columnId) return
  const normalized = Math.max(MIN_COLUMN_WIDTH, Math.round(width))
  const column = columnById(table, columnId)
  if (column) {
    column.width = normalized
    column.realWidth = null
  }
  for (const col of tableCols(el).filter((item) => item.getAttribute('name') === columnId)) {
    col.setAttribute('width', String(normalized))
    col.style.width = `${normalized}px`
  }
  syncOverflowCellWidth(el, columnId, normalized)
}

function fillRemainingWidth(el: HTMLElement, target: ResizeTarget) {
  const viewportWidth = tableViewportWidth(el)
  if (!viewportWidth) return

  const cells = uniqueHeaderCells(el)
  const measuredWidth = cells.reduce((total, cell) => {
    const columnId = columnIdForCell(cell)
    return total + (primaryColWidth(el, columnId) || Math.round(cell.getBoundingClientRect().width))
  }, 0)
  const remaining = Math.floor(viewportWidth - measuredWidth)
  if (remaining <= 1) return

  const filler = [...cells].reverse().find((cell) => (
    isDataHeaderCell(cell) &&
    !cell.classList.contains('hfl-table-actions-col') &&
    !cell.classList.contains('el-table-fixed-column--left') &&
    !cell.classList.contains('el-table-fixed-column--right')
  )) ?? [...cells].reverse().find(isDataHeaderCell)
  const fillerId = columnIdForCell(filler ?? target.th) ?? target.columnId
  if (!fillerId) return

  const current = primaryColWidth(el, fillerId) || Math.round(filler?.getBoundingClientRect().width ?? 0)
  setColumnWidth(el, target.table, fillerId, current + remaining)
}

function applyWidth(el: HTMLElement, target: ResizeTarget, width: number) {
  const normalized = Math.max(MIN_COLUMN_WIDTH, Math.round(width))
  if (target.column) {
    target.column.width = normalized
    target.column.realWidth = null
  }
  for (const col of targetCols(el, target)) {
    col.setAttribute('width', String(normalized))
    col.style.width = `${normalized}px`
  }
  syncOverflowCellWidth(el, target.columnId, normalized)
  fillRemainingWidth(el, target)
  if (target.table) {
    queueTableLayout(el, target.table)
  }
}

function proxyLeft(el: HTMLElement, clientX: number) {
  return clientX - el.getBoundingClientRect().left
}

function showProxy(el: HTMLElement, state: ResizeState, clientX: number) {
  state.proxy.style.left = `${proxyLeft(el, clientX)}px`
  state.proxy.style.display = 'block'
}

function hideProxy(state: ResizeState) {
  state.proxy.style.display = 'none'
}

function createProxy() {
  const proxy = document.createElement('div')
  proxy.className = 'hfl-column-resize-proxy'
  proxy.style.display = 'none'
  return proxy
}

function setHotHeader(state: ResizeState, th: HTMLTableCellElement | null) {
  if (state.hotTh === th) return
  state.hotTh?.classList.remove(RESIZE_HOT_CLASS)
  state.hotTh = th
  state.hotTh?.classList.add(RESIZE_HOT_CLASS)
}

function install(el: HTMLElement, vnode?: VNode) {
  if (stateByElement.has(el)) return

  const table = tableInstanceForVNode(vnode) ?? tableInstanceForElement(el)
  if (table) tableByElement.set(el, table)

  const proxy = createProxy()
  const finishDrag = () => {
    const drag = state.drag
    state.drag = null
    if (drag) {
      document.body.style.userSelect = drag.previousUserSelect
      document.body.style.cursor = drag.previousCursor
      if (el.hasPointerCapture?.(drag.pointerId)) {
        try {
          el.releasePointerCapture(drag.pointerId)
        } catch {
          // Pointer capture may already be released by the browser.
        }
      }
    }
    el.style.cursor = ''
    setHotHeader(state, null)
    el.classList.remove('hfl-resizable-table--dragging')
    hideProxy(state)
    document.removeEventListener('pointermove', state.onDocumentPointerMove)
    document.removeEventListener('pointerup', state.onDocumentPointerUp)
    document.removeEventListener('pointercancel', state.onDocumentPointerCancel)
    window.removeEventListener('blur', state.onWindowBlur)
    if (drag) {
      window.requestAnimationFrame(() => {
        if (el.isConnected) el.dispatchEvent(new Event(COLUMN_RESIZED_EVENT))
      })
    }
  }
  const state: ResizeState = {
    drag: null,
    hotTh: null,
    proxy,
    onPointerMove: (event) => {
      if (state.drag) return
      const target = findResizeTarget(el, event)
      setHotHeader(state, target?.th ?? null)
      el.style.cursor = target ? 'col-resize' : ''
    },
    onPointerDown: (event) => {
      if (event.button !== 0) return
      const target = findResizeTarget(el, event)
      if (!target) return

      event.preventDefault()
      event.stopPropagation()

      state.drag = {
        target,
        pointerId: event.pointerId,
        startX: event.clientX,
        startWidth: currentWidth(el, target),
        previousUserSelect: document.body.style.userSelect,
        previousCursor: document.body.style.cursor,
      }
      try {
        el.setPointerCapture?.(event.pointerId)
      } catch {
        // Pointer capture is best-effort; document listeners still handle cleanup.
      }
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'
      setHotHeader(state, target.th)
      el.classList.add('hfl-resizable-table--dragging')
      showProxy(el, state, event.clientX)
      document.addEventListener('pointermove', state.onDocumentPointerMove)
      document.addEventListener('pointerup', state.onDocumentPointerUp)
      document.addEventListener('pointercancel', state.onDocumentPointerCancel)
      window.addEventListener('blur', state.onWindowBlur)
    },
    onPointerLeave: () => {
      if (!state.drag) {
        el.style.cursor = ''
        setHotHeader(state, null)
      }
    },
    onDocumentPointerMove: (event) => {
      if (!state.drag) return
      const width = state.drag.startWidth + event.clientX - state.drag.startX
      applyWidth(el, state.drag.target, width)
      showProxy(el, state, event.clientX)
    },
    onDocumentPointerUp: () => {
      finishDrag()
    },
    onDocumentPointerCancel: () => {
      finishDrag()
    },
    onLostPointerCapture: () => {
      finishDrag()
    },
    onWindowBlur: () => {
      finishDrag()
    },
  }

  el.classList.add('hfl-resizable-table')
  el.appendChild(proxy)
  el.addEventListener('pointermove', state.onPointerMove)
  el.addEventListener('pointerdown', state.onPointerDown)
  el.addEventListener('pointerleave', state.onPointerLeave)
  el.addEventListener('lostpointercapture', state.onLostPointerCapture)
  stateByElement.set(el, state)
}

function uninstall(el: HTMLElement) {
  const state = stateByElement.get(el)
  if (!state) return

  document.removeEventListener('pointermove', state.onDocumentPointerMove)
  document.removeEventListener('pointerup', state.onDocumentPointerUp)
  document.removeEventListener('pointercancel', state.onDocumentPointerCancel)
  window.removeEventListener('blur', state.onWindowBlur)
  if (state.drag) {
    document.body.style.userSelect = state.drag.previousUserSelect
    document.body.style.cursor = state.drag.previousCursor
    if (el.hasPointerCapture?.(state.drag.pointerId)) {
      try {
        el.releasePointerCapture(state.drag.pointerId)
      } catch {
        // Pointer capture may already be released by the browser.
      }
    }
  }
  el.removeEventListener('pointermove', state.onPointerMove)
  el.removeEventListener('pointerdown', state.onPointerDown)
  el.removeEventListener('pointerleave', state.onPointerLeave)
  el.removeEventListener('lostpointercapture', state.onLostPointerCapture)
  const layoutFrame = layoutFrameByElement.get(el)
  if (layoutFrame) {
    window.cancelAnimationFrame(layoutFrame)
    layoutFrameByElement.delete(el)
  }
  el.classList.remove('hfl-resizable-table', 'hfl-resizable-table--dragging')
  setHotHeader(state, null)
  state.proxy.remove()
  stateByElement.delete(el)
  tableByElement.delete(el)
}

export function setupTableColumnResizeDirective(app: App) {
  app.directive('table-column-resize', {
    mounted: install,
    updated: (el, _binding, vnode) => {
      const table = tableInstanceForVNode(vnode) ?? tableInstanceForElement(el)
      if (table) tableByElement.set(el, table)
    },
    unmounted: uninstall,
  })
}
