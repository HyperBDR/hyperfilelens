import type { App } from 'vue'
import { layoutElTable, tableFromElement, type TableLike } from '../lib/tableScrollSync'

type SyncState = {
  cleanup: () => void
  retryTimer: number | null
}

const stateByElement = new WeakMap<HTMLElement, SyncState>()

function detach(el: HTMLElement) {
  const state = stateByElement.get(el)
  if (!state) return
  if (state.retryTimer !== null) window.clearTimeout(state.retryTimer)
  state.cleanup()
  stateByElement.delete(el)
}

function scrollTargets(el: HTMLElement): HTMLElement[] {
  const wrap = el.querySelector<HTMLElement>('.el-scrollbar__wrap')
  const body = el.querySelector<HTMLElement>('.el-table__body-wrapper')
  const targets = [wrap, body].filter((node): node is HTMLElement => node instanceof HTMLElement)
  return [...new Set(targets)]
}

function syncFromDom(el: HTMLElement, event?: Event) {
  const header = el.querySelector<HTMLElement>('.el-table__header-wrapper')
  const footer = el.querySelector<HTMLElement>('.el-table__footer-wrapper')
  if (!header) return false

  const target = event?.target
  const wrap = el.querySelector<HTMLElement>('.el-scrollbar__wrap')
  const scrollLeft =
    target instanceof HTMLElement && Number.isFinite(target.scrollLeft)
      ? target.scrollLeft
      : wrap?.scrollLeft ?? 0

  header.scrollLeft = scrollLeft
  if (footer) footer.scrollLeft = scrollLeft

  const table = tableFromElement(el)
  table?.setScrollLeft?.(scrollLeft)
  return true
}

function attach(el: HTMLElement) {
  detach(el)

  const header = el.querySelector('.el-table__header-wrapper')
  const targets = scrollTargets(el)
  if (!header || targets.length === 0) return false

  const onScroll = (event: Event) => {
    syncFromDom(el, event)
  }

  for (const target of targets) {
    target.addEventListener('scroll', onScroll, { passive: true })
  }

  const resizeObserver = new ResizeObserver(() => {
    layoutElTable(tableFromElement(el) as TableLike | null)
    syncFromDom(el)
  })
  resizeObserver.observe(el)
  const inner = el.querySelector('.el-table__inner-wrapper')
  if (inner) resizeObserver.observe(inner)

  layoutElTable(tableFromElement(el) as TableLike | null)
  syncFromDom(el)

  stateByElement.set(el, {
    retryTimer: null,
    cleanup: () => {
      for (const target of targets) {
        target.removeEventListener('scroll', onScroll)
      }
      resizeObserver.disconnect()
    },
  })
  return true
}

function scheduleAttach(el: HTMLElement, attempt = 0) {
  if (attach(el)) return
  if (attempt >= 80) return

  const retryTimer = window.setTimeout(() => scheduleAttach(el, attempt + 1), 50)
  stateByElement.set(el, {
    retryTimer,
    cleanup: () => {},
  })
}

export function setupTableHeaderScrollSyncDirective(app: App) {
  app.directive('table-header-scroll-sync', {
    mounted: (el) => scheduleAttach(el as HTMLElement),
    updated: (el) => scheduleAttach(el as HTMLElement),
    unmounted: (el) => detach(el as HTMLElement),
  })
}
