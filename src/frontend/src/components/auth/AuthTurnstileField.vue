<script setup lang="ts">
import { ref } from 'vue'
import { ShieldCheck } from 'lucide-vue-next'

import TurnstileWidget from '../TurnstileWidget.vue'

defineProps<{
  pending: boolean
  ready: boolean
  blocked: boolean
  siteKey: string
  action: string
  loadingMessage: string
  blockedMessage: string
  retryLabel: string
  errorMessage?: string
}>()

const emit = defineEmits<{
  retry: []
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
    v-if="pending || ready || blocked"
    class="auth-turnstile-field"
  >
    <div
      v-if="pending"
      class="auth-turnstile-field__control auth-turnstile-field__loading"
      role="status"
    >
      <span class="auth-turnstile-field__spinner" aria-hidden="true" />
      <span>{{ loadingMessage }}</span>
    </div>

    <div
      v-else-if="ready && siteKey"
      class="auth-turnstile-field__control auth-turnstile-field__widget"
    >
      <TurnstileWidget
        ref="turnstileWidgetRef"
        :site-key="siteKey"
        :action="action"
        theme="dark"
        size="flexible"
        @success="emit('success', $event)"
        @expire="emit('expire')"
        @error="emit('error')"
        @load-failed="emit('load-failed')"
      />
    </div>

    <div
      v-else-if="blocked"
      class="auth-turnstile-field__control auth-turnstile-field__blocked"
      role="alert"
    >
      <ShieldCheck :size="18" aria-hidden="true" />
      <span class="auth-turnstile-field__blocked-text">{{ blockedMessage }}</span>
      <button type="button" class="auth-turnstile-field__retry" @click="emit('retry')">
        {{ retryLabel }}
      </button>
    </div>

    <p v-if="errorMessage && !blocked" class="auth-turnstile-field__error" role="alert">
      {{ errorMessage }}
    </p>
  </div>
</template>

<style scoped>
.auth-turnstile-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.auth-turnstile-field__control {
  box-sizing: border-box;
  width: 100%;
  min-height: 64px;
  display: flex;
  align-items: center;
}

.auth-turnstile-field__loading,
.auth-turnstile-field__blocked {
  gap: 10px;
  padding: 12px 16px;
  background: #313131;
  border: 1px solid #3a3b40;
  border-radius: var(--radius-card);
  overflow: hidden;
  color: #b6b7bb;
  font-size: 14px;
}

.auth-turnstile-field__widget {
  justify-content: center;
  padding: 0;
  background: transparent;
  border: 0;
  border-radius: 0;
  overflow: visible;
}

.auth-turnstile-field__spinner {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: auth-turnstile-spin 0.8s linear infinite;
}

.auth-turnstile-field__blocked-text {
  flex: 1;
  min-width: 0;
}

.auth-turnstile-field__retry {
  min-width: 44px;
  min-height: 44px;
  padding: 0 12px;
  color: var(--color-primary);
  background: transparent;
  border: 1px solid currentColor;
  border-radius: 8px;
  cursor: pointer;
}

.auth-turnstile-field__retry:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.auth-turnstile-field__error {
  margin: 0;
  color: var(--color-error);
  font-size: 12px;
  line-height: 1.4;
}

@keyframes auth-turnstile-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .auth-turnstile-field__spinner { animation: none; }
}
</style>
