<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CheckCircle2, CircleX, ExternalLink, Link2, RefreshCw, ServerCog } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import { apiErrorMessage } from '../../../lib/api'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { fetchPlatformIntegrations, type PlatformIntegration } from '../../lib/platformOpsApi'

const sideNav = usePlatformOpsSideNav()
const integrations = ref<PlatformIntegration[]>([])
const loading = ref(false)
const configured = computed(() => integrations.value.filter((row) => row.configured).length)
const healthy = computed(() => integrations.value.filter((row) => row.reachable && row.authenticated).length)
const unhealthy = computed(() => integrations.value.filter((row) => row.configured && (!row.reachable || !row.authenticated)).length)

function integrationStatus(row: PlatformIntegration) {
  if (!row.configured) return 'Not Configured'
  if (!row.reachable) return 'Unavailable'
  return row.authenticated ? 'Healthy' : 'Degraded'
}

function publicServiceUrl(row: PlatformIntegration) {
  return row.gateway_base_url || row.base_url
}

async function load() {
  loading.value = true
  try { integrations.value = (await fetchPlatformIntegrations()).integrations || [] }
  catch (error) { ElMessage.error({ message: apiErrorMessage(error, 'Failed to load integrations'), grouping: true }) }
  finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="platform-monitoring-page platform-integrations-page">
      <div class="platform-monitoring-page__lead"><p class="platform-monitoring-page__subtitle">Monitor deployment-managed service connections used by HyperFileLens.</p><el-button class="hfl-refresh-button" title="Refresh" :disabled="loading" @click="load"><RefreshCw :size="16" :class="{ 'is-spinning': loading }" /></el-button></div>
      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard label="Integrations" :value="integrations.length" accent="indigo" accent-side="left"><template #icon><Link2 :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Configured" :value="configured" accent="blue" accent-side="left"><template #icon><ServerCog :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Healthy" :value="healthy" accent="green" accent-side="left"><template #icon><CheckCircle2 :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Needs Attention" :value="unhealthy" accent="red" accent-side="left" :pulse="unhealthy > 0"><template #icon><CircleX :size="16" /></template></OpsStatCard>
      </div>
      <div v-loading="loading" class="platform-integration-grid">
        <article v-for="row in integrations" :key="row.key" class="platform-integration-card">
          <div class="platform-integration-card__head"><div class="platform-integration-card__icon"><Link2 :size="20" /></div><div><h2>{{ row.name }}</h2><p>{{ row.category }}</p></div><PlatformOpsStatusPill :status="integrationStatus(row)" /></div>
          <dl class="platform-integration-card__details">
            <div><dt>Deployment Mode</dt><dd>{{ row.mode }}</dd></div>
            <div><dt>Managed By</dt><dd>{{ row.managed_by }}</dd></div>
            <div><dt>Service URL</dt><dd>{{ row.base_url || 'Not configured' }}</dd></div>
            <div><dt>Gateway URL</dt><dd>{{ row.gateway_base_url || 'Not configured' }}</dd></div>
            <div><dt>Connectivity</dt><dd>{{ row.reachable ? 'Reachable' : 'Unavailable' }}</dd></div>
            <div><dt>Authentication</dt><dd>{{ row.authenticated ? 'Authenticated' : 'Unavailable' }}</dd></div>
          </dl>
          <div class="platform-integration-card__footer"><span>Connection values are managed by deployment environment variables.</span><a v-if="publicServiceUrl(row)" :href="publicServiceUrl(row)" target="_blank" rel="noopener noreferrer">Open service <ExternalLink :size="14" /></a></div>
        </article>
        <el-empty v-if="!loading && integrations.length === 0" description="No platform integrations found" :image-size="72" />
      </div>
    </div>
  </ModulePage>
</template>

<style scoped>
.platform-integration-grid { display: grid; gap: 16px; }
.platform-integration-card { padding: 20px; border: 1px solid var(--color-border, #e9e9ef); border-radius: 12px; background: var(--color-card-bg, #fff); }
.platform-integration-card__head { display: flex; align-items: center; gap: 12px; }
.platform-integration-card__head > div:nth-child(2) { min-width: 0; flex: 1; }
.platform-integration-card__head h2 { margin: 0; color: var(--color-text-title, #1c1c26); font-size: 16px; font-weight: 650; }
.platform-integration-card__head p { margin: 3px 0 0; color: var(--color-text-secondary, #70707e); font-size: 12px; }
.platform-integration-card__icon { display: grid; width: 40px; height: 40px; place-items: center; border-radius: 10px; background: color-mix(in srgb, var(--color-primary, #6d5ef6) 10%, transparent); color: var(--color-primary, #6d5ef6); }
.platform-integration-card__details { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin: 20px 0 0; padding: 18px 0; border-block: 1px solid var(--color-border-light, #f2f2f6); }
.platform-integration-card__details div { min-width: 0; }
.platform-integration-card__details dt { color: var(--color-text-secondary, #70707e); font-size: 11px; }
.platform-integration-card__details dd { margin: 4px 0 0; overflow-wrap: anywhere; color: var(--color-text-primary, #3a3a48); font-size: 13px; font-weight: 550; }
.platform-integration-card__footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 16px; color: var(--color-text-secondary, #70707e); font-size: 12px; }
.platform-integration-card__footer a { display: inline-flex; align-items: center; gap: 5px; color: var(--color-primary, #6d5ef6); text-decoration: none; }
@media (max-width: 900px) { .platform-integration-card__details { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 620px) { .platform-integration-card__details { grid-template-columns: 1fr; } .platform-integration-card__footer { align-items: flex-start; flex-direction: column; } }
</style>
