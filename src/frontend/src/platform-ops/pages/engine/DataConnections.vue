<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ExternalLink, GitBranch, Link2, RefreshCw } from 'lucide-vue-next'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import { apiErrorMessage } from '../../../lib/api'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import { fetchPlatformIntegrations, type PlatformIntegration } from '../../lib/platformOpsApi'

const loading = ref(false)
const sourceLens = ref<PlatformIntegration | null>(null)
const status = computed(() => {
  if (!sourceLens.value?.configured) return 'Not Configured'
  if (!sourceLens.value.reachable) return 'Unavailable'
  return sourceLens.value.authenticated ? 'Healthy' : 'Degraded'
})
const connectionManagerUrl = computed(() => sourceLens.value?.gateway_base_url || sourceLens.value?.base_url || '')

async function load() {
  loading.value = true
  try {
    const data = await fetchPlatformIntegrations()
    sourceLens.value = data.integrations.find((row) => row.key === 'sourcelens') || null
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, 'Failed to load data connections'), grouping: true })
  } finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="hfl-list-shell hfl-list-shell--fill platform-data-connections">
    <div class="platform-monitoring-page__lead"><p class="platform-monitoring-page__subtitle">Manage external source platforms used by SourceLens ingestion and knowledge workflows.</p><el-button class="hfl-refresh-button" title="Refresh" :disabled="loading" @click="load"><RefreshCw :size="16" :class="{ 'is-spinning': loading }" /></el-button></div>
    <HflTablePanel fill>
      <template #toolbar><div class="platform-data-connections__summary"><div class="platform-data-connections__icon"><GitBranch :size="18" /></div><div><strong>Source platform connections</strong><span>GitHub, GitLab, Feishu, and other supported providers</span></div></div></template>
      <template #toolbar-actions><PlatformOpsStatusPill :status="status" /></template>
      <template #table>
        <div v-loading="loading" class="platform-data-connections__body">
          <div class="platform-data-connections__service"><div><Link2 :size="18" /><span><strong>SourceLens Connection Manager</strong><small>{{ connectionManagerUrl || 'SourceLens is not configured' }}</small></span></div><a v-if="connectionManagerUrl && sourceLens?.authenticated" :href="connectionManagerUrl" target="_blank" rel="noopener noreferrer">Open Connection Manager <ExternalLink :size="14" /></a></div>
          <el-alert v-if="!sourceLens?.configured" title="Configure the SourceLens bridge before creating data connections." type="warning" :closable="false" show-icon />
          <el-alert v-else-if="!sourceLens.authenticated" title="SourceLens connection management is unavailable until the service connection is healthy." type="error" :closable="false" show-icon />
          <p class="platform-data-connections__note">Connection credentials remain in SourceLens and are never copied into HyperFileLens. HyperFileLens uses the deployment-managed bridge to open the authenticated connection manager.</p>
        </div>
      </template>
    </HflTablePanel>
  </div>
</template>

<style scoped>
.platform-data-connections { min-height: 0; }
.platform-data-connections__summary { display: flex; align-items: center; gap: 10px; }
.platform-data-connections__summary > div:last-child { display: flex; flex-direction: column; gap: 2px; }
.platform-data-connections__summary strong { color: var(--color-text-title, #1c1c26); font-size: 13px; }
.platform-data-connections__summary span { color: var(--color-text-secondary, #70707e); font-size: 11px; }
.platform-data-connections__icon { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 8px; background: color-mix(in srgb, var(--color-primary, #6d5ef6) 10%, transparent); color: var(--color-primary, #6d5ef6); }
.platform-data-connections__body { display: flex; flex-direction: column; gap: 16px; padding: 20px; }
.platform-data-connections__service { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px; border: 1px solid var(--color-border, #e9e9ef); border-radius: 10px; background: var(--color-grey-1, #fafafa); }
.platform-data-connections__service > div { display: flex; align-items: center; gap: 12px; min-width: 0; }
.platform-data-connections__service span { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.platform-data-connections__service strong { color: var(--color-text-title, #1c1c26); font-size: 13px; }
.platform-data-connections__service small { overflow: hidden; color: var(--color-text-secondary, #70707e); text-overflow: ellipsis; white-space: nowrap; }
.platform-data-connections__service a { display: inline-flex; flex-shrink: 0; align-items: center; gap: 5px; color: var(--color-primary, #6d5ef6); font-size: 13px; text-decoration: none; }
.platform-data-connections__note { max-width: 760px; margin: 0; color: var(--color-text-secondary, #70707e); font-size: 12px; line-height: 1.6; }
@media (max-width: 620px) { .platform-data-connections__service { align-items: flex-start; flex-direction: column; } }
</style>
