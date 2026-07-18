<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import ModulePage from '../../../../components/ModulePage.vue'
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
  google_client_id: '',
  google_client_secret: '',
})

async function load() {
  busy.value = true
  try {
    const data = await fetchPlatformIdentitySettings()
    meta.value = data
    form.google_client_id = data.google_client_id || ''
    form.google_client_secret = ''
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
      google_client_id: form.google_client_id,
    }
    if (form.google_client_secret.trim()) body.google_client_secret = form.google_client_secret
    meta.value = await patchPlatformIdentitySettings(body)
    form.google_client_secret = ''
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
      <div class="platform-settings__toolbar">
        <p class="platform-settings__intro">{{ t('platformOps.settings.googleOAuth.intro') }}</p>
        <el-button type="primary" :loading="saving" @click="save">
          {{ t('platformOps.settings.saveChanges') }}
        </el-button>
      </div>

      <div class="platform-settings__panel">
        <el-form label-position="top" class="platform-settings__form">
          <el-form-item :label="t('platformOps.settings.identity.googleClientId')">
            <el-input v-model="form.google_client_id" autocomplete="off" />
          </el-form-item>
          <el-form-item :label="t('platformOps.settings.identity.googleClientSecret')">
            <el-input
              v-model="form.google_client_secret"
              type="password"
              show-password
              autocomplete="new-password"
              :placeholder="meta?.google_client_secret_configured ? '••••••••' : ''"
            />
          </el-form-item>
          <el-form-item :label="t('platformOps.settings.identity.googleRedirect')">
            <el-input :model-value="meta?.google_oauth_redirect_uri || '—'" disabled />
            <p class="platform-settings__hint">{{ t('platformOps.settings.googleOAuth.redirectHint') }}</p>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </ModulePage>
</template>
