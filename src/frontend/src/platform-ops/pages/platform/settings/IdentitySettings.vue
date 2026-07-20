<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import ModulePage from '../../../../components/ModulePage.vue'
import PlatformOpsRefreshButton from '../../../components/PlatformOpsRefreshButton.vue'
import { usePlatformOpsSideNav } from '../../../composables/usePlatformOpsSideNav'
import {
  fetchPlatformIdentitySettings,
  patchPlatformIdentitySettings,
  type PlatformIdentitySettings,
} from '../../../lib/platformOpsApi'
import { apiErrorMessage } from '../../../../lib/api'

const { t } = useI18n()
const sideNav = usePlatformOpsSideNav()

const busy = ref(false)
const saving = ref(false)
const meta = ref<PlatformIdentitySettings | null>(null)
const form = reactive({
  email_signup_enabled: false,
  self_service_password_reset: true,
  platform_ops_enabled: true,
  platform_ops_allowed_cidrs: '',
  registration_verification_code_minutes: 10,
  registration_token_expiry_hours: 24,
  password_reset_verification_code_minutes: 10,
  password_reset_timeout_seconds: 3600,
})

async function load() {
  busy.value = true
  try {
    const data = await fetchPlatformIdentitySettings()
    meta.value = data
    form.email_signup_enabled = data.email_signup_enabled
    form.self_service_password_reset = data.self_service_password_reset
    form.platform_ops_enabled = data.platform_ops_enabled
    form.platform_ops_allowed_cidrs = (data.platform_ops_allowed_cidrs || []).join(', ')
    form.registration_verification_code_minutes = data.iam.registration_verification_code_minutes
    form.registration_token_expiry_hours = data.iam.registration_token_expiry_hours
    form.password_reset_verification_code_minutes = data.iam.password_reset_verification_code_minutes
    form.password_reset_timeout_seconds = data.iam.password_reset_timeout_seconds
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.settings.loadFailed')), grouping: true })
  } finally {
    busy.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const body: Record<string, unknown> = {
      email_signup_enabled: form.email_signup_enabled,
      self_service_password_reset: form.self_service_password_reset,
      platform_ops_enabled: form.platform_ops_enabled,
      platform_ops_allowed_cidrs: form.platform_ops_allowed_cidrs,
      iam: {
        registration_verification_code_minutes: form.registration_verification_code_minutes,
        registration_token_expiry_hours: form.registration_token_expiry_hours,
        password_reset_verification_code_minutes: form.password_reset_verification_code_minutes,
        password_reset_timeout_seconds: form.password_reset_timeout_seconds,
      },
    }
    meta.value = await patchPlatformIdentitySettings(body)
    ElMessage.success({ message: t('platformOps.settings.saveSuccess'), grouping: true })
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.settings.saveFailed')), grouping: true })
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div v-loading="busy" class="platform-settings">
      <el-form label-position="top" class="platform-settings__form">
        <el-form-item :label="t('platformOps.settings.identity.emailSignup')">
          <el-switch v-model="form.email_signup_enabled" />
        </el-form-item>
        <el-form-item :label="t('platformOps.settings.identity.passwordReset')">
          <el-switch v-model="form.self_service_password_reset" />
        </el-form-item>
        <el-form-item :label="t('platformOps.settings.identity.platformOps')">
          <el-switch v-model="form.platform_ops_enabled" />
        </el-form-item>
        <el-form-item :label="t('platformOps.settings.identity.opsCidrs')">
          <el-input v-model="form.platform_ops_allowed_cidrs" :placeholder="t('platformOps.settings.identity.opsCidrsHint')" />
        </el-form-item>

        <h3 class="platform-settings__section">{{ t('platformOps.settings.identity.iamTitle') }}</h3>
        <el-form-item :label="t('platformOps.settings.identity.regCodeMinutes')">
          <el-input-number v-model="form.registration_verification_code_minutes" :min="1" :max="120" />
        </el-form-item>
        <el-form-item :label="t('platformOps.settings.identity.regTokenHours')">
          <el-input-number v-model="form.registration_token_expiry_hours" :min="1" :max="168" />
        </el-form-item>
        <el-form-item :label="t('platformOps.settings.identity.resetCodeMinutes')">
          <el-input-number v-model="form.password_reset_verification_code_minutes" :min="1" :max="120" />
        </el-form-item>
        <el-form-item :label="t('platformOps.settings.identity.resetTimeoutSeconds')">
          <el-input-number v-model="form.password_reset_timeout_seconds" :min="60" :max="86400" />
        </el-form-item>
      </el-form>

      <div class="platform-settings__footer">
        <PlatformOpsRefreshButton :loading="busy" @click="load" />
        <el-button type="primary" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
      </div>
    </div>
  </ModulePage>
</template>
