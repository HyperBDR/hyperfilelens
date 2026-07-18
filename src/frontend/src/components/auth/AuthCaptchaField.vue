<script setup lang="ts">
import { ref } from 'vue'
import { Key } from 'lucide-vue-next'

import TurnstileWidget from '../TurnstileWidget.vue'

const props = defineProps<{
  modelValue: string
  isCaptchaPending?: boolean
  isImageCaptcha: boolean
  isTurnstile: boolean
  isCaptchaBlocked?: boolean
  siteKey: string
  placeholder: string
  loadingMessage?: string
  blockedMessage?: string
  retryLabel?: string
  codeImg: string
  errorMessage?: string
  showError?: boolean
  tabindex?: number | string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'clear-error': []
  refresh: []
  enter: []
  success: [token: string]
  expire: []
  error: []
  'load-failed': []
}>()

const turnstileWidgetRef = ref<InstanceType<typeof TurnstileWidget> | null>(null)

function reset() {
  turnstileWidgetRef.value?.reset()
}

defineExpose({ reset })
</script>

<template>
  <div
    class="auth-captcha-field"
    :class="{ 'has-error': showError }"
  >
    <div
      v-if="props.isCaptchaPending"
      class="auth-captcha-field__control auth-captcha-field__loading"
    >
      <span
        class="auth-captcha-field__spinner"
        aria-hidden="true"
      />
      <span class="auth-captcha-field__loading-text">
        {{ loadingMessage || placeholder }}
      </span>
    </div>

    <div
      v-else-if="props.isImageCaptcha"
      class="auth-captcha-field__control auth-captcha-field__control--image"
    >
      <div class="auth-captcha-field__image-row">
        <div class="auth-captcha-field__input">
          <Key
            class="auth-captcha-field__icon"
            :size="18"
          />
          <input
            :value="modelValue"
            type="text"
            :placeholder="placeholder"
            :tabindex="tabindex"
            autocomplete="off"
            @input="emit('update:modelValue', ($event.target as HTMLInputElement).value); emit('clear-error')"
            @keyup.enter="emit('enter')"
          >
        </div>

        <button
          type="button"
          class="auth-captcha-field__image-button"
          :aria-label="placeholder"
          @click="emit('refresh')"
        >
          <img
            v-if="codeImg"
            :src="codeImg"
            alt="captcha"
            class="auth-captcha-field__image"
          >
          <span
            v-else
            class="auth-captcha-field__image-fallback"
          >
            K K a n
          </span>
        </button>
      </div>
    </div>

    <div
      v-else-if="props.isTurnstile && props.siteKey"
      class="auth-captcha-field__control auth-captcha-field__turnstile-shell"
    >
      <div class="auth-captcha-field__turnstile-viewport">
        <TurnstileWidget
          ref="turnstileWidgetRef"
          :site-key="siteKey"
          theme="dark"
          size="flexible"
          @success="emit('success', $event)"
          @expire="emit('expire')"
          @error="emit('error')"
          @load-failed="emit('load-failed')"
        />
      </div>
    </div>

    <div
      v-else-if="props.isCaptchaBlocked"
      class="auth-captcha-field__control auth-captcha-field__blocked"
    >
      <Key
        class="auth-captcha-field__icon"
        :size="18"
      />
      <span class="auth-captcha-field__blocked-text">
        {{ blockedMessage || errorMessage || placeholder }}
      </span>
      <button
        type="button"
        class="auth-captcha-field__blocked-retry"
        @click="emit('refresh')"
      >
        {{ retryLabel || 'Retry' }}
      </button>
    </div>

    <p
      v-if="showError"
      class="auth-captcha-field__error"
    >
      {{ errorMessage }}
    </p>
  </div>
</template>

<style scoped>
.auth-captcha-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  --auth-captcha-control-height: 64px;
  --auth-captcha-input-height: 34px;
  --auth-captcha-bg: #313131;
  --auth-captcha-border: #3A3B40;
  --auth-captcha-muted-border: rgba(255, 255, 255, 0.1);
}

.auth-captcha-field__control {
  width: 100%;
  display: flex;
  align-items: center;
  background: var(--auth-captcha-bg);
  border: 1px solid var(--auth-captcha-border);
  border-radius: var(--radius-card);
  overflow: hidden;
  transition: border-color 0.2s, background-color 0.2s;
}

.auth-captcha-field__control:focus-within {
  border-color: var(--color-primary);
}

.auth-captcha-field__control--image {
  padding: 3px 12px;
}

.auth-captcha-field__image-row {
  display: flex;
  gap: 12px;
  width: 100%;
  align-items: center;
}

.auth-captcha-field__input {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  height: var(--auth-captcha-input-height);
  padding: 0 4px;
  transition: border-color 0.2s, background-color 0.2s;
}

.auth-captcha-field__input:focus-within {
  border-color: var(--color-primary);
}

.auth-captcha-field__icon {
  flex-shrink: 0;
  margin-right: 10px;
  color: #888A8F;
}

.auth-captcha-field__input input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  outline: none;
  font-size: 14px;
  color: #fff;
}

.auth-captcha-field__input input::placeholder {
  color: #6A6C71;
}

.auth-captcha-field__image-button {
  flex: 0 0 90px;
  width: 90px;
  height: var(--auth-captcha-input-height);
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.12);
  border-radius: var(--radius-card);
  transition: border-color 0.2s, background-color 0.2s;
  position: relative;
  right: -7px;
}

.auth-captcha-field__image-button:hover {
  background: rgba(139, 92, 246, 0.08);
}

.auth-captcha-field__image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.auth-captcha-field__image-fallback {
  width: 96%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.92);
  color: #E91E63;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
  user-select: none;
}

.auth-captcha-field__turnstile-shell {
  width: 100%;
  min-height: var(--auth-captcha-control-height);
  padding: 0;
  align-items: stretch;
  justify-content: stretch;
  background: transparent;
  border: none;
  overflow: visible;
}

.auth-captcha-field__turnstile-viewport {
  width: 100%;
  height: calc(var(--auth-captcha-control-height) - 1px);
  display: block;
  border-radius: var(--radius-card);
  border: 1px solid #3A3B40;
  overflow: hidden;
}

.auth-captcha-field__turnstile-viewport :deep(.turnstile-widget) {
  min-height: var(--auth-captcha-control-height);
  display: block;
  width: calc(100% + 2px);
  margin: -1px;
}

.auth-captcha-field__turnstile-viewport :deep(iframe) {
  display: block;
  width: 100% !important;
  max-width: 100%;
  border: 0 !important;
  background: transparent !important;
}

.auth-captcha-field__turnstile-viewport :deep(.turnstile-widget__loading) {
  height: calc(var(--auth-captcha-control-height) - 1px);
  min-height: 0;
  border: none;
  border-radius: 0;
}

.auth-captcha-field__loading {
  min-height: var(--auth-captcha-control-height);
  padding: 0 12px;
  justify-content: center;
  gap: 10px;
}

.auth-captcha-field__loading-text {
  min-width: 0;
  color: #D4D7DD;
  font-size: 13px;
  line-height: 1.35;
}

.auth-captcha-field__spinner {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border: 2px solid rgba(255, 255, 255, 0.18);
  border-top-color: #8B5CF6;
  border-radius: 999px;
  animation: auth-captcha-spin 0.8s linear infinite;
}

.auth-captcha-field__blocked {
  min-height: var(--auth-captcha-control-height);
  padding: 0 14px 0 15px;
  gap: 2px;
}

.auth-captcha-field__blocked-text {
  flex: 1;
  min-width: 0;
  color: #D4D7DD;
  font-size: 13px;
  line-height: 1.35;
}

.auth-captcha-field__blocked-retry {
  flex-shrink: 0;
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--auth-captcha-muted-border);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  font-size: 12px;
  cursor: pointer;
}

.auth-captcha-field__blocked-retry:hover {
  border-color: var(--color-primary);
}

@keyframes auth-captcha-spin {
  to {
    transform: rotate(360deg);
  }
}

.auth-captcha-field.has-error .auth-captcha-field__input,
.auth-captcha-field.has-error .auth-captcha-field__control {
  border-color: #f85149;
}

.auth-captcha-field__error {
  margin: 0;
  padding-left: 2px;
  font-size: 12px;
  color: #f85149;
}
</style>
