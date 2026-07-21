import { computed, ref } from 'vue'
import { api } from '../lib/api'
import { preloadTurnstileScript } from '../lib/turnstileLoader'

export type TurnstileState = 'pending' | 'disabled' | 'ready' | 'blocked'

interface TurnstileConfigResponse {
  code: string
  data: {
    enabled: boolean
    configured: boolean
    site_key?: string
  }
}

const state = ref<TurnstileState>('pending')
const siteKey = ref('')
const configLoaded = ref(false)
let configLoadPromise: Promise<void> | null = null
const authTurnstileMountGeneration = ref(0)

async function loadTurnstileConfig(force = false): Promise<void> {
  if (configLoadPromise) return configLoadPromise
  if (configLoaded.value && !force) return

  state.value = 'pending'
  configLoadPromise = (async () => {
    try {
      const res = await api<TurnstileConfigResponse>('/api/v1/auth/turnstile/config')
      if (res.code !== '0000' || !res.data) {
        state.value = 'blocked'
        siteKey.value = ''
        return
      }
      if (!res.data.enabled) {
        state.value = 'disabled'
        siteKey.value = ''
        return
      }
      if (!res.data.configured || !res.data.site_key) {
        state.value = 'blocked'
        siteKey.value = ''
        return
      }

      siteKey.value = res.data.site_key
      state.value = 'ready'
      void preloadTurnstileScript()
    } catch {
      state.value = 'blocked'
      siteKey.value = ''
    } finally {
      configLoaded.value = true
      configLoadPromise = null
    }
  })()
  return configLoadPromise
}

export function resetAuthTurnstileSession(): void {
  if (state.value === 'blocked' && siteKey.value) state.value = 'ready'
  authTurnstileMountGeneration.value += 1
}

export function prefetchAuthTurnstile(): void {
  resetAuthTurnstileSession()
  void loadTurnstileConfig()
}

export function useTurnstileConfig() {
  const isTurnstilePending = computed(() => state.value === 'pending')
  const isTurnstileDisabled = computed(() => state.value === 'disabled')
  const isTurnstileReady = computed(() => state.value === 'ready')
  const isTurnstileBlocked = computed(() => state.value === 'blocked')

  function blockTurnstile(): void {
    if (state.value !== 'disabled') state.value = 'blocked'
  }

  function buildTurnstilePayload(token: string): Record<string, string> {
    return isTurnstileReady.value ? { turnstile_token: token } : {}
  }

  return {
    turnstileState: state,
    turnstileSiteKey: siteKey,
    authTurnstileMountGeneration,
    isTurnstilePending,
    isTurnstileDisabled,
    isTurnstileReady,
    isTurnstileBlocked,
    loadTurnstileConfig,
    buildTurnstilePayload,
    blockTurnstile,
  }
}
