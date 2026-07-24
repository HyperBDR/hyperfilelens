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
          'error-callback'?: () => void
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
    action: string
  }>(),
  {
    theme: 'dark',
    size: 'flexible',
    language: undefined,
    loadTimeoutMs: TURNSTILE_LOAD_TIMEOUT_MS,
  },
)

const { locale, t } = useI18n()

const effectiveLanguage = computed(() =>
  props.language ?? turnstileLanguageFromAppLocale(String(locale.value)),
)

const emit = defineEmits<{
  success: [token: string]
  expire: []
  error: []
  'load-failed': []
}>()

const containerRef = ref<HTMLElement | null>(null)
const widgetId = ref<string | null>(null)
const loadTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null)
const frameCheckId = ref<ReturnType<typeof setInterval> | null>(null)
const isLoading = ref(true)
const successEmitted = ref(false)

function emitSuccess(token: string) {
  if (successEmitted.value) return
  successEmitted.value = true
  isLoading.value = false
  clearLoadTimeout()
  clearFrameCheck()
  emit('success', token)
}

function readTurnstileTokenFromContainer(): string {
  const container = containerRef.value
  if (!container) return ''
  const input = container.querySelector<HTMLInputElement>('input[name="cf-turnstile-response"]')
  return input?.value?.trim() ?? ''
}

function markReadyIfWidgetPresent(): boolean {
  const container = containerRef.value
  if (!container) return false

  const token = readTurnstileTokenFromContainer()
  if (token) {
    emitSuccess(token)
    return true
  }

  if (container.querySelector('iframe')) {
    isLoading.value = false
    clearLoadTimeout()
    clearFrameCheck()
    return true
  }

  return false
}

function failLoad() {
  clearLoadTimeout()
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

function clearFrameCheck() {
  if (frameCheckId.value !== null) {
    clearInterval(frameCheckId.value)
    frameCheckId.value = null
  }
}

function failWidget() {
  if (markReadyIfWidgetPresent()) return
  clearLoadTimeout()
  clearFrameCheck()
  isLoading.value = false
  emit('error')
}

function renderWidget() {
  if (!containerRef.value || !window.turnstile || !props.siteKey) {
    failLoad()
    return
  }

  if (widgetId.value) {
    window.turnstile.remove(widgetId.value)
    widgetId.value = null
  }

  containerRef.value.innerHTML = ''
  isLoading.value = true
  successEmitted.value = false
  clearFrameCheck()
  try {
    widgetId.value = window.turnstile.render(containerRef.value, {
      sitekey: props.siteKey,
      theme: props.theme,
      size: props.size,
      language: effectiveLanguage.value,
      appearance: 'always',
      action: props.action,
      callback: (token: string) => {
        emitSuccess(token)
      },
      'expired-callback': () => emit('expire'),
      'error-callback': () => {
        if (markReadyIfWidgetPresent()) return
        failWidget()
      },
    })
    frameCheckId.value = setInterval(() => {
      markReadyIfWidgetPresent()
    }, 100)
    loadTimeoutId.value = setTimeout(() => {
      if (!markReadyIfWidgetPresent()) {
        failWidget()
      }
    }, props.loadTimeoutMs)
  } catch {
    failLoad()
  }
}

function mountWidget() {
  if (!window.turnstile?.render) {
    throw new Error('Turnstile API missing')
  }
  // preloadTurnstileScript() already waits for the API; render immediately.
  // turnstile.ready() can fail to invoke callbacks after SPA remounts.
  renderWidget()
}

async function initWidget(attempt = 0) {
  isLoading.value = true
  if (!props.siteKey) {
    failLoad()
    return
  }
  try {
    await preloadTurnstileScript(props.loadTimeoutMs)
    mountWidget()
  } catch {
    if (attempt < 1) {
      resetTurnstileScriptLoad()
      await new Promise((resolve) => setTimeout(resolve, 300))
      return initWidget(attempt + 1)
    }
    failLoad()
  }
}

function reset() {
  if (widgetId.value && window.turnstile) {
    window.turnstile.reset(widgetId.value)
  } else {
    void initWidget()
  }
}

onMounted(() => {
  void initWidget()
})

watch(
  () => [props.siteKey, props.action, props.theme, props.size, props.language, effectiveLanguage.value] as const,
  () => {
    void initWidget()
  },
)

watch(effectiveLanguage, () => {
  emit('expire')
})

onBeforeUnmount(() => {
  clearLoadTimeout()
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
  min-height: 65px;
  display: block;
  position: relative;
}

.turnstile-widget__container {
  width: 100%;
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
