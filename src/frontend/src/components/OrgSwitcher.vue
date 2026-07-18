<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../lib/api'
import { asList } from '../lib/parse'
import {
  fetchCurrentUser,
  getEffectiveOrgKey,
  setStoredOrgKey,
} from '../composables/useAuth'

type OrgRow = {
  id: number
  key: string
  name: string
}

const { t } = useI18n()
const orgs = ref<OrgRow[]>([])
const loading = ref(false)
const currentKey = computed(() => getEffectiveOrgKey())

const showSwitcher = computed(() => orgs.value.length > 1)

async function loadOrgs() {
  loading.value = true
  try {
    const data = await api<unknown>('/api/v1/iam/orgs/')
    orgs.value = asList<OrgRow>(data)
  } catch {
    orgs.value = []
  } finally {
    loading.value = false
  }
}

async function onOrgChange(orgKey: string) {
  if (!orgKey || orgKey === currentKey.value) return
  setStoredOrgKey(orgKey)
  await fetchCurrentUser()
  window.location.reload()
}

onMounted(() => {
  void loadOrgs()
})
</script>

<template>
  <div v-if="showSwitcher" class="org-switcher">
    <label class="org-switcher__label" for="org-switcher-select">{{ t('nav.orgSwitcher') }}</label>
    <select
      id="org-switcher-select"
      class="org-switcher__select"
      :disabled="loading"
      :value="currentKey"
      @change="onOrgChange(($event.target as HTMLSelectElement).value)"
    >
      <option v-for="org in orgs" :key="org.key" :value="org.key">
        {{ org.name }}
      </option>
    </select>
  </div>
</template>

<style scoped>
.org-switcher {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-right: 8px;
}

.org-switcher__label {
  font-size: 12px;
  color: var(--tz-color, rgba(255, 255, 255, 0.72));
  white-space: nowrap;
}

.org-switcher__select {
  max-width: 180px;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid var(--tz-border, rgba(255, 255, 255, 0.12));
  background: var(--tz-bg, rgba(255, 255, 255, 0.06));
  color: var(--tnav-text, #fff);
  font-size: 12px;
}
</style>
