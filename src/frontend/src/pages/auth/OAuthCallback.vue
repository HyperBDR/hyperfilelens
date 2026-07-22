<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

import { fetchCurrentUser, setStoredOrgKey } from '../../composables/useAuth'
import { resolvePostLoginPath } from '../../composables/useDeployProfile'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const loading = ref(true)

onMounted(async () => {
  const orgKey = route.query.org_key
  if (typeof orgKey === 'string' && orgKey.trim()) {
    setStoredOrgKey(orgKey.trim())
  }

  const user = await fetchCurrentUser()
  loading.value = false

  if (user) {
    router.replace(await resolvePostLoginPath())
    return
  }

  ElMessage.error({ message: t('login.googleLoginFailed'), grouping: true })
  router.replace('/login')
})
</script>

<template>
  <div class="oauth-callback">
    <p>{{ loading ? t('login.googleCompleting') : t('login.googleRedirecting') }}</p>
  </div>
</template>

<style scoped>
.oauth-callback {
  min-height: var(--app-viewport-height);
  display: flex;
  align-items: center;
  justify-content: center;
  background: #08090c;
  color: #fff;
}
</style>
