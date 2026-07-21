<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Mail, Lock, Globe, Eye, EyeOff } from 'lucide-vue-next'
import { api } from '../../lib/api'
import { useAuth, setStoredOrgKey, fetchCurrentUser } from '../../composables/useAuth'
import { useLocaleSwitch } from '../../composables/useLocaleSwitch'
import { useTurnstileConfig } from '../../composables/useTurnstileConfig'
import AuthTurnstileField from '../../components/auth/AuthTurnstileField.vue'
import ResetPasswordCard from '../../components/auth/ResetPasswordCard.vue'
import { fetchDeployProfile, resolvePostLoginPath } from '../../composables/useDeployProfile'
import { appConfig } from '../../lib/appConfig'

const emailSignupEnabled = ref(false)
const showEula = appConfig.showEula
const { t, locale } = useI18n()
const {
  canSwitchLocale,
  nextLocaleCode,
  nextLocaleLabel,
  toggleLocale: switchLocale,
} = useLocaleSwitch()
const router = useRouter()
const route = useRoute()
const sessionNoticeDismissed = ref(false)

const {
  turnstileSiteKey,
  isTurnstilePending,
  isTurnstileReady,
  isTurnstileBlocked,
  authTurnstileMountGeneration,
  loadTurnstileConfig,
  buildTurnstilePayload,
  blockTurnstile,
} = useTurnstileConfig()

const { setUser } = useAuth()
const turnstileToken = ref('')
const turnstileError = ref('')
const turnstileFieldRef = ref<InstanceType<typeof AuthTurnstileField> | null>(null)
const googleEnabled = ref(false)
const googleLoginUrl = ref('/accounts/google/login/?process=login')
const googleLoading = ref(false)

const SESSION_REASON_MESSAGE_KEYS: Record<string, string> = {
  TOKEN_EXPIRED: 'login.sessionExpired',
  REFRESH_EXPIRED: 'login.sessionExpired',
  OTHER_DEVICE_LOGIN: 'login.sessionOtherDevice',
  PASSWORD_CHANGED: 'login.sessionPasswordChanged',
  ACCOUNT_DISABLED: 'login.sessionAccountDisabled',
  TOKEN_REUSED: 'login.sessionTokenReused',
  INVALID_TOKEN: 'login.sessionInvalid',
  TOKEN_BLACKLISTED: 'login.sessionInvalid',
}

// Session invalid error codes that should show a dialog
const SESSION_INVALID_CODES = [
  'OTHER_DEVICE_LOGIN',
  'PASSWORD_CHANGED',
  'ACCOUNT_DISABLED',
  'TOKEN_REUSED',
]

const formItems = reactive({
  email: {
    value: '',
    required: true,
    prop: 'email',
    icon: 'email',
    type: 'text' as const,
    placeholder: '',
    errorMsg: '',
    showError: false,
  },
  password: {
    value: '',
    required: true,
    prop: 'password',
    placeholder: '',
    type: 'password' as const,
    icon: 'password',
    errorMsg: '',
    showError: false,
  },
})

const emailFromQuery = route.query.email
if (typeof emailFromQuery === 'string' && emailFromQuery.trim()) {
  formItems.email.value = emailFromQuery.trim().toLowerCase()
}

const sessionNoticeMessage = computed(() => {
  if (sessionNoticeDismissed.value) return ''
  const reason = route.query.reason
  if (typeof reason !== 'string') return ''
  const key = SESSION_REASON_MESSAGE_KEYS[reason]
  return key ? t(key) : ''
})

function dismissSessionNotice() {
  sessionNoticeDismissed.value = true
}

// Initialize placeholders from i18n
formItems.email.placeholder = t('login.emailPh')
formItems.password.placeholder = t('login.passwordPh')
const submitLoading = ref(false)
const showPassword = ref(false)
const cardView = ref<'login' | 'reset'>('login')
const resetStep = ref<'request' | 'reset'>('request')

// Email validation
const regEmail = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/

function checkMail(value: string) {
  if (!value) {
    return t('login.emailErrRequired')
  }
  if (!regEmail.test(value)) {
    return t('login.emailErrFormat')
  }
  return ''
}

// Password validation: 8-20 chars, must contain letters and digits
function checkPassword(value: string) {
  if (!value) {
    return t('login.passwordErrRequired')
  }
  const pattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d.!"@#$%&'*():;\\+/=?^_`{|}~><-]{8,20}$/
  if (!pattern.test(value)) {
    return t('login.passwordErrFormat')
  }
  return ''
}

// Real-time email validation
function validateEmailOnInput() {
  const error = checkMail(formItems.email.value)
  if (error && formItems.email.value) {
    formItems.email.errorMsg = error
    formItems.email.showError = true
  } else {
    formItems.email.errorMsg = ''
    formItems.email.showError = false
  }
}

// Real-time password validation
function validatePasswordOnInput() {
  const error = checkPassword(formItems.password.value)
  if (error && formItems.password.value) {
    formItems.password.errorMsg = error
    formItems.password.showError = true
  } else {
    formItems.password.errorMsg = ''
    formItems.password.showError = false
  }
}

// Password strength calculation
const passwordStrength = computed(() => {
  const pwd = formItems.password.value
  if (!pwd) return { level: 0, text: '' }

  let score = 0
  if (pwd.length >= 8) score++
  if (pwd.length >= 12) score++
  if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++
  if (/\d/.test(pwd)) score++
  if (/[!"@#$%&'*():;\\+/=?^_`{|}~><-]/.test(pwd)) score++

  if (score <= 2) return { level: 1, text: t('login.passwordWeak'), color: 'var(--color-error)' }
  if (score <= 3) return { level: 2, text: t('login.passwordMedium'), color: 'var(--color-warning)' }
  return { level: 3, text: t('login.passwordStrong'), color: 'var(--color-success)' }
})

function blockUnavailableTurnstile() {
  blockTurnstile()
  turnstileToken.value = ''
  turnstileError.value = t('login.captchaUnavailable')
}

async function retryTurnstile() {
  turnstileToken.value = ''
  turnstileError.value = ''
  await loadTurnstileConfig(true)
}

function resetTurnstile() {
  if (!isTurnstileReady.value) return
  turnstileToken.value = ''
  turnstileFieldRef.value?.reset()
}

function onTurnstileSuccess(token: string) {
  turnstileToken.value = token
  turnstileError.value = ''
}

function onTurnstileExpire() {
  turnstileToken.value = ''
}

function onTurnstileError() {
  blockUnavailableTurnstile()
}

function onTurnstileLoadFailed() {
  blockUnavailableTurnstile()
}

function validateForm() {
  let hasError = false

  const emailError = checkMail(formItems.email.value)
  if (emailError) {
    formItems.email.errorMsg = emailError
    formItems.email.showError = true
    hasError = true
  } else {
    formItems.email.errorMsg = ''
    formItems.email.showError = false
  }

  const passwordError = checkPassword(formItems.password.value)
  if (passwordError) {
    formItems.password.errorMsg = passwordError
    formItems.password.showError = true
    hasError = true
  } else {
    formItems.password.errorMsg = ''
    formItems.password.showError = false
  }

  if (isTurnstilePending.value) {
    turnstileError.value = t('login.captchaLoading')
    hasError = true
  } else if (isTurnstileBlocked.value) {
    turnstileError.value = t('login.captchaUnavailable')
    hasError = true
  } else if (isTurnstileReady.value) {
    if (!turnstileToken.value) {
      turnstileError.value = t('login.captchaErrRequired')
      hasError = true
    } else {
      turnstileError.value = ''
    }
  } else {
    turnstileError.value = ''
  }

  return !hasError
}

function showSessionErrorDialog(errorCode: string) {
  const message = t(SESSION_REASON_MESSAGE_KEYS[errorCode] || 'login.sessionExpired')
  ElMessageBox.alert(message, t('login.sessionExpired'), {
    confirmButtonText: t('login.btnSubmit'),
    type: 'warning',
  }).then(() => {
    router.push('/login')
  })
}

async function resolveLoginTargetPath(): Promise<string> {
  const redirect = route.query.redirect
  if (
    typeof redirect === 'string' &&
    redirect.startsWith('/') &&
    !redirect.startsWith('//') &&
    !redirect.startsWith('/login')
  ) {
    return redirect
  }
  return resolvePostLoginPath()
}

async function handleSubmit() {
  if (submitLoading.value) return

  if (!validateForm()) return

  submitLoading.value = true
  setStoredOrgKey('')

  formItems.email.errorMsg = ''
  formItems.email.showError = false
  formItems.password.errorMsg = ''
  formItems.password.showError = false
  turnstileError.value = ''

  try {
    const postData = {
      email: formItems.email.value,
      password: formItems.password.value,
      ...buildTurnstilePayload(turnstileToken.value),
    }

    const res = await api<{
      code: string
      data: {
        user?: { id: number; email: string; username: string }
        roles?: string[]
        available_orgs?: Array<{ org_key: string; org_name: string; role: string }>
        message?: string
        error?: {
          fields?: Record<string, string[]>
          message?: string
        }
      }
      error?: {
        error_code?: string
        fields?: Record<string, string[]>
        message?: string
      }
    }>('/api/v1/auth/email-login', {
      method: 'POST',
      body: JSON.stringify(postData),
    })

    if (res.code !== '0000') {
      // Check for session invalid errors
      const errorCode = res.error?.error_code
      if (errorCode && SESSION_INVALID_CODES.includes(errorCode)) {
        showSessionErrorDialog(errorCode)
        return
      }

      // Error can be in either res.error or res.data.error
      const fields = res.error?.fields || res.data?.error?.fields
      if (fields && Object.keys(fields).length > 0) {
        handleFieldsError(fields)
      } else {
        ElMessage.error({ message: res.error?.message || res.data?.error?.message || t('login.msgLoginFailed'), grouping: true })
      }
      return
    }

    // Auto-login with the first available organization
    const orgs = res.data.available_orgs || []
    if (orgs.length > 0) {
      await completeLoginWithOrg(orgs[0].org_key)
      return
    }

    // No orgs - login successful (shouldn't happen normally)
    if (res.data.user) {
      setUser(res.data.user)
    }
    router.push(await resolveLoginTargetPath())
  } catch (err: unknown) {
    const errObj = err as { status?: number; message?: string; errorCode?: string; code?: string; fields?: Record<string, string[]> }

    // Check for session invalid errors
    if (errObj.errorCode && SESSION_INVALID_CODES.includes(errObj.errorCode)) {
      showSessionErrorDialog(errObj.errorCode)
      return
    }

    const fields = errObj.fields
    if (fields && Object.keys(fields).length > 0) {
      handleFieldsError(fields)
    } else {
      resetTurnstile()
      ElMessage.error({ message: errObj.message || t('login.msgLoginFailed'), grouping: true })
    }
  } finally {
    submitLoading.value = false
  }
}

async function completeLoginWithOrg(orgKey: string) {
  try {
    const res = await api<{
      code: string
      status?: number
      data: {
        user?: { id: number; email: string; username: string }
        selected_org?: { org_key: string; org_name: string; role: string }
        message?: string
        code?: string
        error?: {
          message?: string
        }
      }
      error?: {
        message?: string
      }
    }>('/api/v1/auth/org-select', {
      method: 'POST',
      body: JSON.stringify({ org_key: orgKey }),
    })

    if (res.code !== '0000') {
      const isSessionExpired = res.status === 401 || res.data?.code === '1001'
      if (isSessionExpired) {
        ElMessage.error({ message: t('login.sessionExpired'), grouping: true })
        resetTurnstile()
        return
      }
      ElMessage.error({ message: res.error?.message || res.data?.error?.message || t('login.msgLoginFailed'), grouping: true })
      resetTurnstile()
      return
    }

    setStoredOrgKey(orgKey)
    await fetchCurrentUser()

    router.push(await resolveLoginTargetPath())
  } catch (err: unknown) {
    const errObj = err as { message?: string; status?: number }
    if (errObj.status === 401) {
      ElMessage.error({ message: t('login.sessionExpired'), grouping: true })
      resetTurnstile()
    } else {
      ElMessage.error({ message: errObj.message || t('login.msgLoginFailed'), grouping: true })
      resetTurnstile()
    }
  }
}

function handleFieldsError(fields?: Record<string, string[]>) {
  if (!fields) return

  if (fields.turnstile_token) {
    resetTurnstile()
  } else if (fields.password && isTurnstileReady.value) {
    // Turnstile tokens are single-use; refresh while the user corrects their password.
    resetTurnstile()
  }

  // Known error message translations
  const errorMessageMap: Record<string, string> = {
    'Invalid or expired human verification': t('login.captchaInvalid'),
    'Incorrect password': t('login.passwordErrIncorrect'),
  }

  for (const [fieldName, messages] of Object.entries(fields)) {
    let message = Array.isArray(messages) ? messages[0] : messages
    // Translate known error messages
    if (errorMessageMap[message]) {
      message = errorMessageMap[message]
    }
    switch (fieldName) {
      case 'email':
        formItems.email.errorMsg = message
        formItems.email.showError = true
        break
      case 'password':
        formItems.password.errorMsg = message
        formItems.password.showError = true
        break
      case 'turnstile_token':
        turnstileError.value = message
        break
      default:
        break
    }
  }
}

function goRegister() {
  router.push('/register')
}

function goForgetPwd() {
  cardView.value = 'reset'
  resetStep.value = 'request'
}

function backToLogin(email?: string) {
  if (email) {
    formItems.email.value = email
  }
  cardView.value = 'login'
  resetStep.value = 'request'
}

function onResetStepChange(step: 'request' | 'reset') {
  resetStep.value = step
}

const cardTitle = computed(() => {
  if (cardView.value === 'login') return t('login.welcomeTitle')
  if (resetStep.value === 'reset') return t('findPwd.updateTitle')
  return t('findPwd.welcomeTitle')
})

const canSubmitLogin = computed(() => {
  if (submitLoading.value) return false
  if (isTurnstilePending.value) return false
  if (isTurnstileBlocked.value) return false
  if (isTurnstileReady.value) return Boolean(turnstileToken.value)
  return true
})

function toggleLocale() {
  switchLocale()
  formItems.email.placeholder = t('login.emailPh')
  formItems.password.placeholder = t('login.passwordPh')
}

async function loadGoogleConfig() {
  try {
    const res = await api<{
      code: string
      data: { enabled: boolean; login_url?: string }
    }>('/api/v1/auth/google/config')
    if (res.code === '0000' && res.data?.enabled) {
      googleEnabled.value = true
      if (res.data.login_url) {
        googleLoginUrl.value = res.data.login_url
      }
    }
  } catch {
    googleEnabled.value = false
  }
}

function startGoogleLogin() {
  if (!googleEnabled.value || googleLoading.value) return
  googleLoading.value = true
  setStoredOrgKey('')
  window.location.assign(googleLoginUrl.value)
}

onMounted(async () => {
  turnstileToken.value = ''
  void loadGoogleConfig()
  const profile = await fetchDeployProfile()
  emailSignupEnabled.value = !!profile?.email_signup_enabled
  await loadTurnstileConfig()
})
</script>

<template>
  <div class="login-container">
    <!-- Background image layer -->
    <div class="bg-image"></div>

    <!-- Left Banner -->
    <div class="left-logo">
      <div class="flex flex-col items-start w-full">
        <div class="auth-brand-panel">
          <span class="auth-logo-mark" aria-hidden="true">
            <span class="auth-logo-mark__beam auth-logo-mark__beam--a"></span>
            <span class="auth-logo-mark__beam auth-logo-mark__beam--b"></span>
            <span class="auth-logo-mark__core"></span>
          </span>
          <div class="auth-brand-copy">
            <span class="auth-logo-text"><span>Hyper</span><strong>FileLens</strong></span>
            <p class="!text-lg !font-medium !tracking-wide !text-white !mb-2">{{ t('login.brandDesc') }}</p>
            <p class="auth-brand-slogan">
              {{ t('login.brandSlogan') }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Login Form Box -->
    <div class="login-form-box">
      <div class="login-box-title" :class="{ 'title-en': locale === 'en' }">
        <span :class="{ '!text-base': locale === 'en' }">
          {{ cardTitle }}
        </span>
        <button
          v-if="canSwitchLocale"
          class="lang-toggle"
          @click="toggleLocale"
          :title="`Switch to ${nextLocaleLabel}`"
        >
          <Globe :size="18" />
          <span class="lang-label">{{ nextLocaleCode.toUpperCase() }}</span>
        </button>
      </div>

      <Transition name="card-view-fade" mode="out-in">
        <ResetPasswordCard
          v-if="cardView === 'reset'"
          key="reset"
          class="login-box-content"
          :initial-email="formItems.email.value"
          @back-to-login="backToLogin"
          @update:step="onResetStepChange"
        />

        <div v-else key="login" class="login-box-content">
        <ElAlert
          v-if="sessionNoticeMessage"
          class="session-alert"
          type="warning"
          :title="sessionNoticeMessage"
          show-icon
          :closable="true"
          @close="dismissSessionNotice"
        />

        <!-- Email -->
        <div class="input-wrapper" :class="{ 'has-error': formItems.email.showError }">
          <div class="input-row">
            <Mail class="input-icon" :size="18" />
            <input
              v-model="formItems.email.value"
              type="text"
              :placeholder="formItems.email.placeholder"
              tabindex="1"
              autocomplete="email"
              @blur="validateEmailOnInput"
              @input="validateEmailOnInput"
            />
          </div>
          <p v-if="formItems.email.showError" class="error-msg">{{ formItems.email.errorMsg }}</p>
        </div>

        <!-- Password -->
        <div class="input-wrapper" :class="{ 'has-error': formItems.password.showError }">
          <div class="input-row">
            <Lock class="input-icon" :size="18" />
            <input
              v-model="formItems.password.value"
              :type="showPassword ? 'text' : 'password'"
              :placeholder="formItems.password.placeholder"
              tabindex="2"
              autocomplete="current-password"
              @blur="validatePasswordOnInput"
              @input="validatePasswordOnInput"
              @keyup.enter="handleSubmit"
            />
            <button
              type="button"
              class="eye-btn"
              @mousedown.prevent="showPassword = true"
              @mouseup="showPassword = false"
              @mouseleave="showPassword = false"
            >
              <EyeOff v-if="showPassword" class="eye-icon" :size="16" />
              <Eye v-else class="eye-icon" :size="16" />
            </button>
          </div>
          <!-- Password strength indicator -->
          <div v-if="formItems.password.value" class="strength-bar-wrapper">
            <div class="strength-bar">
              <div
                class="strength-fill"
                :style="{ width: (passwordStrength.level / 3 * 100) + '%', background: passwordStrength.color }"
              ></div>
            </div>
            <span class="strength-text" :style="{ color: passwordStrength.color }">{{ passwordStrength.text }}</span>
          </div>
          <p v-if="formItems.password.showError" class="error-msg">{{ formItems.password.errorMsg }}</p>
        </div>

        <AuthTurnstileField
          :key="authTurnstileMountGeneration"
          ref="turnstileFieldRef"
          :pending="isTurnstilePending"
          :ready="isTurnstileReady"
          :blocked="isTurnstileBlocked"
          :site-key="turnstileSiteKey"
          action="login"
          :loading-message="t('login.captchaLoading')"
          :blocked-message="t('login.captchaUnavailable')"
          :retry-label="t('login.captchaRetry')"
          :error-message="turnstileError"
          @retry="retryTurnstile"
          @success="onTurnstileSuccess"
          @expire="onTurnstileExpire"
          @error="onTurnstileError"
          @load-failed="onTurnstileLoadFailed"
        />

        <div>
          <!-- Submit Button -->
          <ElButton
            type="primary"
            class="submit-btn"
            :disabled="submitLoading || !canSubmitLogin"
            :loading="submitLoading"
            @click="handleSubmit"
          >
            {{ submitLoading ? t('login.btnSubmitLoading') : t('login.btnSubmit') }}
          </ElButton>

          <!-- Forgot Password -->
          <div class="forgot-row">
            <a href="#" class="forgot-link" @click.prevent="goForgetPwd">{{ t('login.forgotPwd') }}</a>
          </div>
        </div>

        <!-- Divider -->
        <div v-if="googleEnabled" class="divider-row">
          <div class="divider-line"></div>
          <span class="divider-text">{{ t('login.dividerOr') }}</span>
          <div class="divider-line"></div>
        </div>

        <!-- Third Party -->
        <div v-if="googleEnabled" class="google-signin-block">
          <button
            type="button"
            class="google-btn"
            :disabled="googleLoading"
            @click="startGoogleLogin"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25C22.56 11.47 22.49 10.73 22.36 10H12V14.26H17.92C17.66 15.63 16.89 16.8 15.72 17.58V20.34H19.28C21.36 18.42 22.56 15.6 22.56 12.25Z" fill="#4285F4"/>
              <path d="M12 23C14.97 23 17.46 22.02 19.28 20.34L15.72 17.58C14.74 18.24 13.48 18.66 12 18.66C9.13999 18.66 6.70999 16.73 5.83999 14.12H2.17999V16.96C3.98999 20.55 7.7 23 12 23Z" fill="#34A853"/>
              <path d="M5.84 14.12C5.62 13.46 5.49 12.75 5.49 12C5.49 11.25 5.61 10.54 5.84 9.88001V7.04001H2.18C1.43 8.53001 1 10.22 1 12C1 13.78 1.43 15.47 2.18 16.96L5.84 14.12Z" fill="#FBBC05"/>
              <path d="M12 5.34001C13.62 5.34001 15.06 5.89001 16.21 6.99001L19.36 3.84001C17.46 2.07001 14.97 1 12 1C7.7 1 3.99 3.45001 2.18 7.04001L5.84 9.88001C6.71 7.27001 9.14 5.34001 12 5.34001Z" fill="#EA4335"/>
            </svg>
            <span>{{ t('login.googleBtn') }}</span>
          </button>
        </div>

        <!-- Footer: Register + EULA -->
        <div class="login-footer">
          <div v-if="emailSignupEnabled" class="footer-row">
            <span class="footer-text">{{ t('login.noAccount') }}</span>
            <a href="#" class="footer-link sign-up-link" @click.prevent="goRegister">{{ t('login.freeRegister') }}</a>
          </div>
          <p
            v-if="showEula"
            class="footer-legal"
          >
            {{ t('login.eulaText') }}
            <a
              class="footer-link"
              href="https://oneprocloud.com/eula"
              target="_blank"
              rel="noopener noreferrer">
              {{ $t('login.eulaNoticeLinkText') }}
            </a>{{ t('login.eulaSuffix') }}
          </p>
        </div>
      </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  user-select: none;
  width: 100%;
  height: 100vh;
  background-color: #08090C;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
}

.bg-image {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-image: url('/assets/bg.png');
  background-size: cover;
  background-position: center;
  opacity: 0.6;
}

.left-logo {
  width: 600px;
  margin-right: 8%;
  min-width: 600px;
  z-index: 10;
  display: flex;
  align-items: center;
}

.auth-brand-panel {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 32px;
}

.auth-brand-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.auth-brand-slogan {
  margin: 0;
  color: var(--color-primary);
  font-size: 14px;
  font-weight: 500;
  letter-spacing: normal;
  line-height: 1.4;
  white-space: nowrap;
}

.auth-logo-mark {
  position: relative;
  width: 72px;
  height: 72px;
  flex: 0 0 72px;
  border: 2px solid #8b5cf6;
  border-radius: 10px;
  background: #12111a;
  box-shadow: 0 0 34px rgba(139, 92, 246, 0.5);
  filter: drop-shadow(0 0 22px rgba(139, 92, 246, 0.52));
  transform: rotate(45deg);
}

.auth-logo-mark::before {
  content: '';
  position: absolute;
  inset: 16px;
  background: #a78bfa;
  border-radius: 2px;
}

.auth-logo-mark__beam,
.auth-logo-mark__core {
  display: none;
}

.auth-logo-text {
  display: inline-flex;
  align-items: baseline;
  gap: 0;
  font-size: 48px;
  font-weight: 850;
  color: #fff;
  letter-spacing: 0;
  line-height: 1;
}

.auth-logo-text > span {
  color: #ffcc4d;
  font-weight: 850;
}

.auth-logo-text strong {
  color: #f8fafc;
  font-weight: 850;
}

.login-form-box {
  min-width: 440px;
  width: 440px;
  padding: 40px;
  background-color: hsla(0, 0%, 100%, .1);
  border-radius: var(--radius-card);
  box-shadow: 0px 4px 4px 0px rgba(0, 0, 0, .25);
  border: 1px solid rgba(255, 255, 255, 0.05);
  z-index: 10;
}

.login-box-title {
  display: flex;
  justify-content: space-between;
  font-size: 22px !important;
  font-weight: 600;
  color: #FFF;
}
.login-box-title.title-en {
  font-size: 20px !important;
}

.lang-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  cursor: pointer;
  color: #fff;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color 0.2s, background 0.2s;
  font-size: 13px;
  font-weight: normal;
}

.lang-toggle:hover {
  background: rgba(255, 255, 255, 0.1);
}

.lang-label {
  font-size: 12px;
}

.login-box-content {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.session-alert {
  --el-alert-padding: 10px 12px;
  border-radius: var(--radius-card);
  line-height: 1.4;
  position: relative;
  padding-right: 42px;
}

.session-alert :deep(.el-alert__title) {
  line-height: 20px;
}

.session-alert :deep(.el-alert__close-btn) {
  top: 50%;
  right: 12px;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transform: translateY(-50%);
  transition: background-color 0.2s, color 0.2s;
}

.session-alert :deep(.el-alert__close-btn:hover),
.session-alert :deep(.el-alert__close-btn:focus-visible) {
  background: rgba(245, 158, 11, 0.16);
  color: #d97706;
}

/* Shared input styles */
.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.input-row {
  display: flex;
  align-items: center;
  background-color: #313131;
  border: 1px solid #3A3B40;
  border-radius: var(--radius-card);
  height: 42px;
  padding: 0 14px;
  transition: border-color 0.2s;
}

.input-row:focus-within {
  border-color: var(--color-primary);
}

.input-icon {
  color: #888A8F;
  flex-shrink: 0;
  margin-right: 12px;
}

.input-row input {
  height: 38px;
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: 14px;
  color: #fff;
}

.input-row input::placeholder {
  color: #6A6C71;
}

.eye-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  margin-left: 8px;
  color: #888A8F;
  border-radius: 4px;
  height: 24px;
  width: 24px;
  justify-content: center;
  transition: color 0.2s, background-color 0.2s;
}

.eye-btn:hover {
  color: #fff;
  background-color: rgba(255, 255, 255, 0.1);
}

/* Error state */
.input-wrapper.has-error .input-row {
  border-color: #f85149;
}

.error-msg {
  font-size: 12px;
  color: #f85149;
  padding-left: 2px;
}

/* Password strength */
.strength-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.strength-bar {
  flex: 1;
  height: 3px;
  background: #3A3B40;
  border-radius: 2px;
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  transition: width 0.3s, background 0.3s;
}

.strength-text {
  font-size: 12px;
  font-weight: 500;
}

/* Submit button */
.submit-btn {
  width: 100%;
  height: 42px !important;
  background: #4A85C6;
  border: none;
  border-radius: 21px;
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.btn-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.submit-btn:hover:not(:disabled) {
  background: #5A95D6;
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Forgot password */
.forgot-row {
  text-align: right;
  padding-top: 4px;
}

.forgot-link {
  font-size: 12px;
  color: #fff;
  text-decoration: none;
  transition: color 0.2s;
}

.forgot-link:hover {
  color: #fff;
}

/* Divider */
.divider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
}

.divider-text {
  font-size: 12px;
  color: #fff;
}

/* Google login */
.google-signin-block {
  width: 100%;
}

.google-btn {
  width: 100%;
  height: 34px;
  background: #fff;
  border: none;
  border-radius: 21px;
  color: #333;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 0.2s;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.google-btn:hover:not(:disabled) {
  background: #f0f0f0;
}

.google-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Login footer area */
.login-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.footer-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.footer-legal {
  width: 100%;
  margin: 0;
  text-align: center;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.38);
}

.footer-legal .footer-link {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.52);
}

.footer-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.footer-link {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  text-decoration: underline;
  transition: color 0.2s;
}

.footer-link:hover {
  color: #fff;
}

.sign-up-link {
  color: var(--color-primary);
  font-weight: 500;
}

.sign-up-link:hover {
  color: #c4b5fd;
}

.card-view-fade-enter-active,
.card-view-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.card-view-fade-enter-from {
  opacity: 0;
  transform: translateX(12px);
}

.card-view-fade-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}
</style>
