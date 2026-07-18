import { computed, ref } from 'vue'
import { api } from '../lib/api'
import { preloadTurnstileScript } from '../lib/turnstileLoader'

export type CaptchaProvider = 'image' | 'turnstile'
export type EffectiveCaptchaProvider = CaptchaProvider | 'pending' | 'blocked'

/** Infra/config issues that make Turnstile unavailable (not user verification failures). */
export type TurnstileInfraFallbackReason =
  | 'widget_error'
  | 'script_load_failed'
  | 'config_unavailable'

/** Max wait before failing closed when Turnstile script/widget does not become ready. */
export const TURNSTILE_LOAD_TIMEOUT_MS = 15000

interface CaptchaConfigResponse {
  code: string
  data: {
    captcha_provider: CaptchaProvider
    turnstile_site_key?: string
    image_fallback_enabled?: boolean
  }
}

const configuredProvider = ref<CaptchaProvider | null>(null)
const effectiveProvider = ref<EffectiveCaptchaProvider>('pending')
const turnstileSiteKey = ref('')
const imageFallbackActive = ref(false)
const configLoaded = ref(false)
const configLoading = ref(false)
let configLoadPromise: Promise<void> | null = null
const reportedInfraFallbackReasons = new Set<TurnstileInfraFallbackReason>()
/** Bumped on each auth-route entry to force captcha widget remount. */
const authCaptchaMountGeneration = ref(0)

/** Report Turnstile infra failure once per reason per page session (for prod log alerting). */
export function reportTurnstileInfraFallback(reason: TurnstileInfraFallbackReason): void {
  if (reportedInfraFallbackReasons.has(reason)) return
  reportedInfraFallbackReasons.add(reason)
  void api('/api/v1/auth/captcha-fallback-report', {
    method: 'POST',
    body: JSON.stringify({ reason }),
  }).catch(() => {
    // Best-effort telemetry; never block UX.
  })
}

async function loadCaptchaConfig(force = false): Promise<void> {
  if (configLoadPromise) return configLoadPromise
  if (configLoaded.value && !force) {
    applyEffectiveProvider()
    return
  }

  void preloadTurnstileScript()
  effectiveProvider.value = 'pending'
  imageFallbackActive.value = false
  configLoading.value = true
  configLoadPromise = (async () => {
    try {
      const res = await api<CaptchaConfigResponse>('/api/v1/auth/captcha-config')
      if (res.code === '0000' && res.data) {
        configuredProvider.value = res.data.captcha_provider === 'turnstile' ? 'turnstile' : 'image'
        turnstileSiteKey.value = res.data.turnstile_site_key || ''
      } else {
        configuredProvider.value = 'turnstile'
        turnstileSiteKey.value = ''
      }
      applyEffectiveProvider()
      configLoaded.value = true
    } catch {
      configuredProvider.value = 'turnstile'
      turnstileSiteKey.value = ''
      activateImageFallback('config_unavailable')
      configLoaded.value = true
    } finally {
      configLoading.value = false
      configLoadPromise = null
    }
  })()
  return configLoadPromise
}

function activateImageFallback(reason: TurnstileInfraFallbackReason): void {
  reportTurnstileInfraFallback(reason)
  effectiveProvider.value = 'image'
  imageFallbackActive.value = true
}

function applyEffectiveProvider() {
  if (!configuredProvider.value) {
    effectiveProvider.value = 'pending'
    imageFallbackActive.value = false
    return
  }
  if (configuredProvider.value === 'turnstile' && turnstileSiteKey.value) {
    effectiveProvider.value = 'turnstile'
    imageFallbackActive.value = false
    return
  }
  if (configuredProvider.value === 'turnstile') {
    activateImageFallback('config_unavailable')
    return
  }
  effectiveProvider.value = 'image'
  imageFallbackActive.value = false
}

/** Remount captcha widgets when re-entering auth pages; keep a loaded Turnstile script when possible. */
export function resetAuthCaptchaSession(): void {
  applyEffectiveProvider()
  authCaptchaMountGeneration.value += 1
}

/** Prefetch captcha config + Turnstile script on auth routes before the page mounts. */
export function prefetchAuthCaptcha(): void {
  resetAuthCaptchaSession()
  void preloadTurnstileScript()
  void loadCaptchaConfig()
}

export function useCaptchaConfig() {
  const isCaptchaPending = computed(() => effectiveProvider.value === 'pending')
  const isTurnstile = computed(() => effectiveProvider.value === 'turnstile')
  const isImageCaptcha = computed(() => effectiveProvider.value === 'image')
  const isCaptchaBlocked = computed(() => effectiveProvider.value === 'blocked')
  const prefersTurnstile = computed(
    () => configuredProvider.value === 'turnstile' && Boolean(turnstileSiteKey.value),
  )

  /** Degrade to image captcha when Turnstile infrastructure is unavailable. */
  function blockTurnstile(reason: TurnstileInfraFallbackReason): boolean {
    if (effectiveProvider.value === 'image') {
      return false
    }
    activateImageFallback(reason)
    return true
  }

  function buildCaptchaPayload(
    imageCaptcha: { id: string; code: string },
    turnstileToken: string,
  ): Record<string, string> {
    if (isTurnstile.value) {
      return { turnstile_token: turnstileToken }
    }
    return { id: imageCaptcha.id, code: imageCaptcha.code }
  }

  return {
    configuredProvider,
    effectiveProvider,
    turnstileSiteKey,
    imageFallbackActive,
    authCaptchaMountGeneration,
    isCaptchaPending,
    isTurnstile,
    isImageCaptcha,
    isCaptchaBlocked,
    prefersTurnstile,
    blockTurnstile,
    loadCaptchaConfig,
    buildCaptchaPayload,
  }
}
