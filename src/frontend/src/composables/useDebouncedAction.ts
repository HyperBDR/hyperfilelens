import { onBeforeUnmount } from 'vue'

export function useDebouncedAction(action: () => void, delay = 900) {
  let timer: ReturnType<typeof window.setTimeout> | undefined

  function cancel() {
    if (!timer) return
    window.clearTimeout(timer)
    timer = undefined
  }

  function schedule() {
    cancel()
    timer = window.setTimeout(() => {
      timer = undefined
      action()
    }, delay)
  }

  function runNow() {
    cancel()
    action()
  }

  onBeforeUnmount(cancel)

  return { schedule, runNow, cancel }
}
