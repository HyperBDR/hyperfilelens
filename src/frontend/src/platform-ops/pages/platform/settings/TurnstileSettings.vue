<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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
  captcha_provider: 'image',
  turnstile_site_key: '',
  turnstile_secret_key: '',
})

const captchaOptions = computed(() => [
  { value: 'image', label: t('platformOps.settings.identity.captchaImage') },
  { value: 'turnstile', label: t('platformOps.settings.identity.captchaTurnstile') },
])

async function load() {
  busy.value = true
  try {
    const data = await fetchPlatformIdentitySettings()
    meta.value = data
    form.captcha_provider = data.captcha_provider || 'image'
    form.turnstile_site_key = data.turnstile_site_key || ''
    form.turnstile_secret_key = ''
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
      captcha_provider: form.captcha_provider,
      turnstile_site_key: form.turnstile_site_key,
    }
    if (form.turnstile_secret_key.trim()) body.turnstile_secret_key = form.turnstile_secret_key
    meta.value = await patchPlatformIdentitySettings(body)
    form.turnstile_secret_key = ''
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
        <p class="platform-settings__intro">{{ t('platformOps.settings.turnstile.intro') }}</p>
        <el-button type="primary" :loading="saving" @click="save">
          {{ t('platformOps.settings.saveChanges') }}
        </el-button>
      </div>

      <div class="platform-settings__panel">
        <el-form label-position="top" class="platform-settings__form">
          <el-form-item :label="t('platformOps.settings.identity.captchaProvider')">
            <el-select v-model="form.captcha_provider">
              <el-option v-for="opt in captchaOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </el-form-item>
          <template v-if="form.captcha_provider === 'turnstile'">
            <el-form-item :label="t('platformOps.settings.identity.turnstileSiteKey')">
              <el-input v-model="form.turnstile_site_key" autocomplete="off" />
            </el-form-item>
            <el-form-item :label="t('platformOps.settings.identity.turnstileSecret')">
              <el-input
                v-model="form.turnstile_secret_key"
                type="password"
                show-password
                autocomplete="new-password"
                :placeholder="meta?.turnstile_secret_configured ? '••••••••' : ''"
              />
              <p class="platform-settings__hint">{{ t('platformOps.settings.turnstile.secretHint') }}</p>
            </el-form-item>
          </template>
        </el-form>
      </div>
    </div>
  </ModulePage>
</template>
