import type { VNode } from 'vue'

export type TableLike = {
  $el?: HTMLElement
  $ready?: boolean
  refs?: {
    scrollBarRef?: { wrapRef?: HTMLElement; update?: () => void }
    headerWrapper?: HTMLElement
    footerWrapper?: HTMLElement
    bodyWrapper?: HTMLElement
    tableInnerWrapper?: HTMLElement
  }
  doLayout?: () => void
  setScrollLeft?: (value: number) => void
  store?: {
    scheduleLayout?: (needUpdateColumns?: boolean, immediate?: boolean) => void
    states?: { columns?: { value?: unknown[] } | unknown[] }
  }
  proxy?: TableLike | null
  exposed?: TableLike | null
  parent?: TableLike | null
}

function hasTableStore(candidate: TableLike | null | undefined) {
  const columns = candidate?.store?.states?.columns
  return Boolean(columns && 'value' in columns ? columns.value?.length : columns)
}

function resolveTableInstance(instance: TableLike | null | undefined): TableLike | null {
  while (instance) {
    const candidates = [instance, instance.proxy, instance.exposed]
    const match = candidates.find((candidate) => hasTableStore(candidate))
    if (match) return match
    instance = instance.parent ?? null
  }
  return null
}

export function tableFromElement(el: HTMLElement, vnode?: VNode): TableLike | null {
  const fromVnode = resolveTableInstance((vnode?.component as TableLike | undefined) ?? null)
  if (fromVnode) return fromVnode
  return resolveTableInstance(
    (el as HTMLElement & { __vueParentComponent?: TableLike | null }).__vueParentComponent ?? null,
  )
}

export function syncTableHeaderScroll(table: TableLike | null | undefined, event?: Event) {
  const el = table?.$el as HTMLElement | undefined
  if (el instanceof HTMLElement) {
    const header = el.querySelector<HTMLElement>('.el-table__header-wrapper')
    const footer = el.querySelector<HTMLElement>('.el-table__footer-wrapper')
    const wrap = el.querySelector<HTMLElement>('.el-scrollbar__wrap')
    const target = event?.target
    const scrollLeft =
      target instanceof HTMLElement && Number.isFinite(target.scrollLeft)
        ? target.scrollLeft
        : wrap?.scrollLeft ?? table?.refs?.scrollBarRef?.wrapRef?.scrollLeft ?? 0

    if (header) header.scrollLeft = scrollLeft
    if (footer) footer.scrollLeft = scrollLeft
    table?.setScrollLeft?.(scrollLeft)
    return
  }

  if (!table?.refs) return

  const wrap = table.refs.scrollBarRef?.wrapRef
  const target = event?.target
  const scrollLeft =
    target instanceof HTMLElement && Number.isFinite(target.scrollLeft)
      ? target.scrollLeft
      : wrap?.scrollLeft ?? 0

  if (table.refs.headerWrapper) table.refs.headerWrapper.scrollLeft = scrollLeft
  if (table.refs.footerWrapper) table.refs.footerWrapper.scrollLeft = scrollLeft
  table.setScrollLeft?.(scrollLeft)
}

export function layoutElTable(table: TableLike | null | undefined) {
  if (!table) return
  if (table.store?.scheduleLayout) {
    table.store.scheduleLayout(false, true)
  } else {
    table.doLayout?.()
  }
  table.refs?.scrollBarRef?.update?.()
  syncTableHeaderScroll(table)
}
