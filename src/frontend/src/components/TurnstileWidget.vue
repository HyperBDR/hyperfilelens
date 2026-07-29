<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  preloadTurnstileScript,
  resetTurnstileScriptLoad,
  TURNSTILE_LOAD_TIMEOUT_MS,
} from '../lib/turnstileLoader'
import { turnstileLanguageFromAppLocale } from '../lib/turnstileLanguage'

declare global {
  interface Window {
    turnstile?: {
      ready: (callback: () => void) => void
      render: (
        container: HTMLElement,
        options: {
          sitekey: string
          callback: (token: string) => void
          'expired-callback'?: () => void
          'error-callback'?: (errorCode?: string) => void
          'response-field'?: boolean
          'response-field-name'?: string
          retry?: 'auto' | 'never'
          'refresh-expired'?: 'auto' | 'manual' | 'never'
          'refresh-timeout'?: 'auto' | 'manual' | 'never'
          theme?: 'light' | 'dark' | 'auto'
          size?: 'normal' | 'compact' | 'flexible'
          language?: string
          appearance?: 'always' | 'execute' | 'interaction-only'
          action?: string
        },
      ) => string
      reset: (widgetId?: string) => void
      remove: (widgetId?: string) => void
    }
  }
}

const props = withDefaults(
  defineProps<{
    siteKey: string
    theme?: 'light' | 'dark' | 'auto'
    size?: 'normal' | 'compact' | 'flexible'
    /** Override Turnstile language; defaults to the current page locale. */
    language?: string
    loadTimeoutMs?: number
    slowLoadDelayMs?: number
    action: string
  }>(),
  {
    theme: 'dark',
    size: 'flexible',
    language: undefined,
    loadTimeoutMs: TURNSTILE_LOAD_TIMEOUT_MS,
    slowLoadDelayMs: 8_000,
  },
)

const { locale, t } = useI18n()

const effectiveLanguage = computed(() =>
  props.language ?? turnstileLanguageFromAppLocale(String(locale.value)),
)

const emit = defineEmits<{
  success: [token: string]
  expire: []
  invalidate: []
  error: [errorCode?: string]
  'load-failed': []
  'slow-load': []
  rendered: []
}>()

const containerRef = ref<HTMLElement | null>(null)
const widgetId = ref<string | null>(null)
const loadTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null)
const slowLoadTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null)
const frameCheckId = ref<ReturnType<typeof setInterval> | null>(null)
const isLoading = ref(true)
const successEmitted = ref(false)
const failureEmitted = ref(false)
let lifecycleGeneration = 0
let isUnmounted = false

function isCurrentGeneration(generation: number): boolean {
  return !isUnmounted && generation === lifecycleGeneration
}

function normalizeTurnstileErrorCode(errorCode?: string): string | undefined {
  const normalized = String(errorCode ?? '').trim()
  return /^\d{3,10}$/.test(normalized) ? normalized : undefined
}

function emitSuccess(token: string, generation = lifecycleGeneration) {
  const normalizedToken = token.trim()
  if (
    !normalizedToken
    || !isCurrentGeneration(generation)
    || successEmitted.value
  ) return
  successEmitted.value = true
  failureEmitted.value = false
  isLoading.value = false
  clearLoadTimeout()
  clearSlowLoadTimeout()
  clearFrameCheck()
  emit('success', normalizedToken)
}

function readTurnstileTokenFromContainer(): string {
  const container = containerRef.value
  if (!container) return ''
  const input = container.querySelector<HTMLInputElement>('input[name="cf-turnstile-response"]')
  return input?.value?.trim() ?? ''
}

function invalidateTurnstileTokenInContainer(): void {
  const input = containerRef.value?.querySelector<HTMLInputElement>(
    'input[name="cf-turnstile-response"]',
  )
  if (input) input.value = ''
}

function markReadyIfWidgetPresent(generation = lifecycleGeneration): boolean {
  if (!isCurrentGeneration(generation)) return false
  const container = containerRef.value
  if (!container) return false

  const responseInput = container.querySelector<HTMLInputElement>(
    'input[name="cf-turnstile-response"]',
  )
  if (responseInput) {
    const token = responseInput.value.trim()
    if (token) {
      emitSuccess(token, generation)
      return true
    }

    isLoading.value = false
    clearLoadTimeout()
    clearSlowLoadTimeout()
    clearFrameCheck()
    emit('rendered')
    return true
  }

  if (container.querySelector('iframe')) {
    isLoading.value = false
    clearLoadTimeout()
    clearSlowLoadTimeout()
    clearFrameCheck()
    emit('rendered')
    return true
  }

  return false
}

function failLoad(generation = lifecycleGeneration) {
  if (!isCurrentGeneration(generation) || failureEmitted.value) return
  failureEmitted.value = true
  clearLoadTimeout()
  clearSlowLoadTimeout()
  clearFrameCheck()
  isLoading.value = false
  emit('load-failed')
}

function clearLoadTimeout() {
  if (loadTimeoutId.value !== null) {
    clearTimeout(loadTimeoutId.value)
    loadTimeoutId.value = null
  }
}

function clearSlowLoadTimeout() {
  if (slowLoadTimeoutId.value !== null) {
    clearTimeout(slowLoadTimeoutId.value)
    slowLoadTimeoutId.value = null
  }
}

function scheduleSlowLoadNotice(generation: number) {
  clearSlowLoadTimeout()
  slowLoadTimeoutId.value = setTimeout(() => {
    slowLoadTimeoutId.value = null
    if (
      isCurrentGeneration(generation)
      && isLoading.value
      && !successEmitted.value
      && !failureEmitted.value
    ) {
      emit('slow-load')
    }
  }, props.slowLoadDelayMs)
}

function clearFrameCheck() {
  if (frameCheckId.value !== null) {
    clearInterval(frameCheckId.value)
    frameCheckId.value = null
  }
}

function failWidget(generation = lifecycleGeneration, errorCode?: string) {
  if (
    !isCurrentGeneration(generation)
    || successEmitted.value
    || failureEmitted.value
  ) return

  const token = readTurnstileTokenFromContainer()
  if (token) {
    emitSuccess(token, generation)
    return
  }

  failureEmitted.value = true
  clearLoadTimeout()
  clearSlowLoadTimeout()
  clearFrameCheck()
  isLoading.value = false
  emit('error', errorCode)
}

function renderWidget(generation: number) {
  if (!isCurrentGeneration(generation)) return
  if (!containerRef.value || !window.turnstile || !props.siteKey) {
    failLoad(generation)
    return
  }

  try {
    if (widgetId.value) {
      window.turnstile.remove(widgetId.value)
      widgetId.value = null
    }

    containerRef.value.innerHTML = ''
    isLoading.value = true
    successEmitted.value = false
    failureEmitted.value = false
    clearLoadTimeout()
    clearFrameCheck()
    widgetId.value = window.turnstile.render(containerRef.value, {
      sitekey: props.siteKey,
      theme: props.theme,
      size: props.size,
      language: effectiveLanguage.value,
      appearance: 'always',
      action: props.action,
      'response-field': true,
      'response-field-name': 'cf-turnstile-response',
      retry: 'never',
      'refresh-expired': 'never',
      'refresh-timeout': 'auto',
      callback: (token: string) => {
        emitSuccess(token, generation)
      },
      'expired-callback': () => handleExpire(generation),
      'error-callback': (errorCode) => {
        failWidget(generation, normalizeTurnstileErrorCode(errorCode))
      },
    })
    if (!isCurrentGeneration(generation) || successEmitted.value || failureEmitted.value) return
    frameCheckId.value = setInterval(() => {
      markReadyIfWidgetPresent(generation)
    }, 100)
    loadTimeoutId.value = setTimeout(() => {
      if (!markReadyIfWidgetPresent(generation)) {
        failWidget(generation)
      }
    }, props.loadTimeoutMs)
  } catch {
    failLoad(generation)
  }
}

function mountWidget(generation: number) {
  if (!isCurrentGeneration(generation)) return
  if (!window.turnstile?.render) {
    throw new Error('Turnstile API missing')
  }
  // preloadTurnstileScript() already waits for the API; render immediately.
  // turnstile.ready() can fail to invoke callbacks after SPA remounts.
  renderWidget(generation)
}

async function initWidget(attempt = 0, generation = ++lifecycleGeneration) {
  if (!isCurrentGeneration(generation)) return
  isLoading.value = true
  if (attempt === 0) scheduleSlowLoadNotice(generation)
  if (!props.siteKey) {
    failLoad(generation)
    return
  }
  try {
    await preloadTurnstileScript(props.loadTimeoutMs)
    if (!isCurrentGeneration(generation)) return
    mountWidget(generation)
  } catch {
    if (!isCurrentGeneration(generation)) return
    if (attempt < 1) {
      resetTurnstileScriptLoad()
      await new Promise((resolve) => setTimeout(resolve, 300))
      if (!isCurrentGeneration(generation)) return
      return initWidget(attempt + 1, generation)
    }
    failLoad(generation)
  }
}

function reset() {
  if (isUnmounted) return
  // A successful token is single-use. Every reset starts a new challenge and
  // gets a fresh lifecycle generation. This rejects callbacks from the old
  // widget without rejecting an identical token returned by Cloudflare test
  // challenges after the new widget is completed.
  invalidateTurnstileTokenInContainer()
  void initWidget()
}

function handleExpire(generation: number) {
  if (!isCurrentGeneration(generation)) return
  clearSlowLoadTimeout()
  emit('expire')
  reset()
}

onMounted(() => {
  void initWidget()
})

watch(
  () => [props.siteKey, props.action, props.theme, props.size, props.language, effectiveLanguage.value] as const,
  () => {
    emit('invalidate')
    void initWidget()
  },
)

onBeforeUnmount(() => {
  isUnmounted = true
  lifecycleGeneration += 1
  clearLoadTimeout()
  clearSlowLoadTimeout()
  clearFrameCheck()
  if (widgetId.value && window.turnstile) {
    window.turnstile.remove(widgetId.value)
    widgetId.value = null
  }
})

defineExpose({ reset })
</script>

<template>
  <div class="turnstile-widget">
    <div
      ref="containerRef"
      class="turnstile-widget__container"
    />
    <div
      v-if="isLoading"
      class="turnstile-widget__loading"
      role="status"
      aria-live="polite"
    >
      <span
        class="turnstile-widget__spinner"
        aria-hidden="true"
      />
      <span>{{ t('login.captchaLoading') }}</span>
    </div>
  </div>
</template>

<style scoped>
.turnstile-widget {
  width: 100%;
  height: 65px;
  min-height: 65px;
  display: block;
  position: relative;
}

.turnstile-widget__container {
  width: 100%;
  height: 100%;
  min-height: 65px;
}

.turnstile-widget__container :deep(iframe) {
  display: block;
  border: 0 !important;
  background: transparent !important;
  width: 100% !important;
  max-width: 100%;
}

.turnstile-widget__loading {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: left !important;
  gap: 10px;
  padding: 0 14px;
  box-sizing: border-box;
  background: #313131;
  border: 1px solid #3A3B40;
  border-radius: var(--radius-card);
  color: #D4D7DD;
  font-size: 13px;
  line-height: 1.35;
  text-align: center;
}

.turnstile-widget__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.18);
  border-top-color: #8B5CF6;
  border-radius: 999px;
  animation: turnstile-widget-spin 0.8s linear infinite;
}

@keyframes turnstile-widget-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
