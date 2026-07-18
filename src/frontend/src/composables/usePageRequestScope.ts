import { onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { isAbortError } from '../lib/api'

type Cleanup = () => void

export function usePageRequestScope() {
  const controllers = new Map<string, AbortController>()
  const cleanups = new Set<Cleanup>()

  function abortScope(scope: string) {
    const controller = controllers.get(scope)
    if (!controller) return
    controller.abort()
    controllers.delete(scope)
  }

  function nextSignal(scope: string) {
    abortScope(scope)
    const controller = new AbortController()
    controllers.set(scope, controller)
    return controller.signal
  }

  function releaseSignal(scope: string, signal: AbortSignal) {
    const controller = controllers.get(scope)
    if (controller?.signal === signal) controllers.delete(scope)
  }

  function isCurrentSignal(scope: string, signal: AbortSignal) {
    return controllers.get(scope)?.signal === signal && !signal.aborted
  }

  function registerCleanup(cleanup: Cleanup) {
    cleanups.add(cleanup)
    return () => cleanups.delete(cleanup)
  }

  function abortAll() {
    for (const controller of controllers.values()) {
      controller.abort()
    }
    controllers.clear()
    for (const cleanup of cleanups) {
      cleanup()
    }
    cleanups.clear()
  }

  async function runScoped<T>(scope: string, fn: (signal: AbortSignal) => Promise<T>) {
    const signal = nextSignal(scope)
    try {
      return await fn(signal)
    } finally {
      releaseSignal(scope, signal)
    }
  }

  async function runLatest<T>(
    scope: string,
    fn: (signal: AbortSignal) => Promise<T>,
  ): Promise<T | undefined> {
    const signal = nextSignal(scope)
    try {
      const result = await fn(signal)
      return isCurrentSignal(scope, signal) ? result : undefined
    } catch (err) {
      if (isAbortError(err)) return undefined
      throw err
    } finally {
      releaseSignal(scope, signal)
    }
  }

  onBeforeUnmount(abortAll)
  onBeforeRouteLeave(() => {
    abortAll()
  })

  return {
    nextSignal,
    releaseSignal,
    isCurrentSignal,
    abortScope,
    abortAll,
    registerCleanup,
    runScoped,
    runLatest,
    isAbortError,
  }
}
