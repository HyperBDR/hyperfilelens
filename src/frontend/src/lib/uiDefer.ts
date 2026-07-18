import { nextTick } from 'vue'

export function releaseStalePopupLock(): void {
  if (typeof document === 'undefined') return
  if (document.querySelector('.el-overlay')) return
  document.body.classList.remove('el-popup-parent--hidden')
}

/** Wait for dropdown/popper teardown before opening another overlay (MessageBox, Dialog). */
export async function afterOverlayDismiss(): Promise<void> {
  await nextTick()
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve())
  })
  releaseStalePopupLock()
}
