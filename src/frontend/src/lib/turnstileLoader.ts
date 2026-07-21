export const TURNSTILE_LOAD_TIMEOUT_MS = 15000

export const TURNSTILE_SCRIPT_ID = 'cf-turnstile-script'
export const TURNSTILE_SCRIPT_SRC =
  'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

declare global {
  interface Window {
    turnstile?: {
      ready: (callback: () => void) => void
      render: (
        container: HTMLElement,
        options: Record<string, unknown>,
      ) => string
      reset: (widgetId?: string) => void
      remove: (widgetId?: string) => void
    }
  }
}

let scriptLoadPromise: Promise<void> | null = null

function remainingTimeoutMs(startedAt: number, timeoutMs: number): number {
  return Math.max(0, timeoutMs - (Date.now() - startedAt))
}

/** Drop a failed/stale script tag so the next preload can inject a clean one. */
export function resetTurnstileScriptLoad(): void {
  scriptLoadPromise = null
  document.getElementById(TURNSTILE_SCRIPT_ID)?.remove()
  delete window.turnstile
}

function waitForTurnstileApi(timeoutMs: number): Promise<void> {
  if (window.turnstile) {
    return Promise.resolve()
  }

  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      reject(new Error('Turnstile API timeout'))
    }, timeoutMs)

    const finish = () => {
      clearTimeout(timeoutId)
      resolve()
    }

    const fail = () => {
      clearTimeout(timeoutId)
      reject(new Error('Turnstile API unavailable'))
    }

    const existing = document.getElementById(TURNSTILE_SCRIPT_ID) as HTMLScriptElement | null
    if (existing?.dataset.turnstileReady === 'true' && window.turnstile) {
      finish()
      return
    }

    if (window.turnstile?.ready) {
      window.turnstile.ready(finish)
      return
    }

    existing?.addEventListener('load', () => {
      if (window.turnstile?.ready) {
        window.turnstile.ready(finish)
      } else if (window.turnstile) {
        finish()
      } else {
        fail()
      }
    }, { once: true })
    existing?.addEventListener('error', fail, { once: true })
  })
}

/** Start loading Cloudflare Turnstile JS early (deduplicated). Safe to call multiple times. */
export function preloadTurnstileScript(
  timeoutMs: number = TURNSTILE_LOAD_TIMEOUT_MS,
): Promise<void> {
  if (window.turnstile) {
    return Promise.resolve()
  }
  if (scriptLoadPromise) {
    return scriptLoadPromise
  }

  scriptLoadPromise = new Promise((resolve, reject) => {
    const startedAt = Date.now()
    const existing = document.getElementById(TURNSTILE_SCRIPT_ID) as HTMLScriptElement | null
    if (existing) {
      waitForTurnstileApi(remainingTimeoutMs(startedAt, timeoutMs) || timeoutMs)
        .then(resolve)
        .catch(reject)
      return
    }

    let outerTimeoutId: ReturnType<typeof setTimeout> | null = setTimeout(() => {
      outerTimeoutId = null
      scriptLoadPromise = null
      reject(new Error('Turnstile script timeout'))
    }, timeoutMs)

    const clearOuterTimeout = () => {
      if (outerTimeoutId !== null) {
        clearTimeout(outerTimeoutId)
        outerTimeoutId = null
      }
    }

    const script = document.createElement('script')
    script.id = TURNSTILE_SCRIPT_ID
    script.src = TURNSTILE_SCRIPT_SRC
    // Dynamically inserted scripts default to async; Turnstile explicit render forbids it.
    script.async = false
    script.onload = () => {
      clearOuterTimeout()
      script.dataset.turnstileReady = 'true'
      waitForTurnstileApi(remainingTimeoutMs(startedAt, timeoutMs) || timeoutMs)
        .then(() => {
          resolve()
        })
        .catch((err) => {
          scriptLoadPromise = null
          reject(err)
        })
    }
    script.onerror = () => {
      clearOuterTimeout()
      scriptLoadPromise = null
      reject(new Error('Turnstile script failed'))
    }
    document.head.appendChild(script)
  })

  return scriptLoadPromise
}
