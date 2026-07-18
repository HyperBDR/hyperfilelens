<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const reason = computed(() => String(route.query.reason || 'unknown'))

const message = computed(() => {
  switch (reason.value) {
    case 'no_email':
      return t('login.googleErrorNoEmail')
    case 'account_disabled':
      return t('login.googleErrorDisabled')
    case 'provision_failed':
      return t('login.googleErrorProvision')
    case 'not_authenticated':
      return t('login.googleErrorNotAuthenticated')
    case 'invalid_grant':
      return t('login.googleErrorInvalidGrant')
    case 'state_lost':
      return t('login.googleErrorStateLost')
    default:
      return t('login.googleLoginFailed')
  }
})

function backToLogin() {
  router.push('/login')
}
</script>

<template>
  <div class="oauth-error">
    <div class="oauth-error-card">
      <h1>{{ t('login.googleErrorTitle') }}</h1>
      <p>{{ message }}</p>
      <button type="button" class="back-btn" @click="backToLogin">
        {{ t('login.backToLogin') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.oauth-error {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #08090c;
  color: #fff;
}

.oauth-error-card {
  width: min(420px, 92vw);
  padding: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid #3a3b40;
  text-align: center;
}

.oauth-error-card h1 {
  margin: 0 0 12px;
  font-size: 20px;
}

.oauth-error-card p {
  margin: 0 0 24px;
  color: #b0b3b8;
  line-height: 1.5;
}

.back-btn {
  border: none;
  border-radius: 999px;
  padding: 10px 24px;
  background: #6366f1;
  color: #fff;
  cursor: pointer;
}
</style>
