<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { BellRing, CircleCheck, CircleOff, RefreshCw, Search, ShieldAlert } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import PlatformOpsPagination from '../../components/PlatformOpsPagination.vue'
import { useDebouncedAction } from '../../../composables/useDebouncedAction'
import { useResponsiveDrawerWidth } from '../../../composables/useResponsiveDrawerWidth'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import PlatformSupportActions from '../../components/PlatformSupportActions.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { fetchPlatformAlertPolicies, type AlertPolicyStats, type PlatformAlertPolicy } from '../../lib/platformOpsApi'

const sideNav = usePlatformOpsSideNav()
const route = useRoute()
const { drawerSize } = useResponsiveDrawerWidth(3)
const rows = ref<PlatformAlertPolicy[]>([])
const stats = ref<AlertPolicyStats>({ total: 0, enabled: 0, disabled: 0, critical: 0 })
const loading = ref(false)
const selected = ref<PlatformAlertPolicy | null>(null)
const drawerOpen = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({ search: '', type: '', severity: '', enabled: '', org: String(route.query.org || '') })
const { schedule: scheduleSearch, runNow: runSearchNow } = useDebouncedAction(applyFilters)

async function load() {
  loading.value = true
  try {
    const data = await fetchPlatformAlertPolicies({ page: pagination.page, page_size: pagination.pageSize, ...filters })
    rows.value = data.results
    stats.value = data.stats || stats.value
    pagination.count = data.count
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, 'Failed to load alert policies'), grouping: true })
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  pagination.page = 1
  void load()
}

function resetFilters() {
  Object.assign(filters, { search: '', type: '', severity: '', enabled: '', org: '' })
  runSearchNow()
}

function openDrawer(row: PlatformAlertPolicy) {
  selected.value = row
  drawerOpen.value = true
}

onMounted(load)
watch(() => filters.search, scheduleSearch)
watch(() => [filters.type, filters.severity, filters.enabled, filters.org], runSearchNow)
watch(() => [pagination.page, pagination.pageSize], load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="platform-monitoring-page">
      <div class="platform-monitoring-page__lead">
        <p class="platform-monitoring-page__subtitle">Review alert conditions across customer accounts. Policies are managed inside each customer account.</p>
        <span class="platform-monitoring-page__updated">Read-only inventory</span>
      </div>
      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard label="Total Policies" :value="stats.total" accent="indigo" accent-side="left"><template #icon><BellRing :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Enabled" :value="stats.enabled" accent="green" accent-side="left"><template #icon><CircleCheck :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Disabled" :value="stats.disabled" accent="orange" accent-side="left"><template #icon><CircleOff :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Critical" :value="stats.critical" accent="red" accent-side="left" :pulse="stats.critical > 0"><template #icon><ShieldAlert :size="16" /></template></OpsStatCard>
      </div>
      <HflTablePanel fill>
        <template #toolbar>
          <div class="platform-monitoring-page__filters">
            <el-input v-model="filters.search" clearable class="platform-monitoring-page__search" placeholder="Search policies or accounts"><template #prefix><Search :size="15" /></template></el-input>
            <el-select v-model="filters.severity" clearable class="platform-monitoring-page__filter" placeholder="Severity">
              <el-option value="critical" label="Critical" /><el-option value="warning" label="Warning" /><el-option value="info" label="Info" />
            </el-select>
            <el-select v-model="filters.enabled" clearable class="platform-monitoring-page__filter" placeholder="Status">
              <el-option value="true" label="Enabled" /><el-option value="false" label="Disabled" />
            </el-select>
            <el-input v-model="filters.type" clearable class="platform-monitoring-page__filter" placeholder="Policy type" />
            <el-input v-model="filters.org" clearable class="platform-monitoring-page__filter" placeholder="Account key" />
            <el-button v-if="Object.values(filters).some(Boolean)" text @click="resetFilters">Reset</el-button>
          </div>
        </template>
        <template #toolbar-utility>
          <el-button class="hfl-refresh-button" title="Refresh" :disabled="loading" @click="load"><RefreshCw :size="16" :class="{ 'is-spinning': loading }" /></el-button>
        </template>
        <template #table="{ tableMaxHeight }">
          <el-table v-loading="loading" :data="rows" stripe flexible row-key="id" class="hfl-list-table" :max-height="tableMaxHeight">
            <el-table-column label="Policy" min-width="250"><template #default="{ row }"><button type="button" class="platform-monitoring-page__title-button" @click="openDrawer(row)">{{ row.name }}</button><span class="platform-monitoring-page__cell-meta" :class="{ 'hfl-empty-mark': !row.description && !row.type }">{{ row.description || row.type || '—' }}</span></template></el-table-column>
            <el-table-column label="Status" width="110"><template #default="{ row }"><PlatformOpsStatusPill :status="row.enabled ? 'Enabled' : 'Disabled'" /></template></el-table-column>
            <el-table-column label="Severity" width="115"><template #default="{ row }"><PlatformOpsStatusPill :status="row.severity" /></template></el-table-column>
            <el-table-column prop="type" label="Type" min-width="150" />
            <el-table-column label="Account" min-width="150"><template #default="{ row }"><PlatformOpsOrgLink :org-id="row.organization" :org-key="row.organization_key" /></template></el-table-column>
            <el-table-column label="Updated" width="170"><template #default="{ row }"><span :class="{ 'hfl-empty-mark': !row.updated_at }">{{ formatLocalDateTime(row.updated_at, '—') }}</span></template></el-table-column>
            <template #empty><el-empty description="No alert policies found" :image-size="72" /></template>
          </el-table>
        </template>
        <template #footer><PlatformOpsPagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" :total="pagination.count" /></template>
      </HflTablePanel>
    </div>
    <el-drawer v-model="drawerOpen" :size="drawerSize" destroy-on-close>
      <template #header><div class="platform-monitoring-drawer__header"><h2>{{ selected?.name }}</h2><p>{{ selected?.organization_name }} · {{ selected?.type }}</p></div></template>
      <template v-if="selected">
        <PlatformSupportActions
          :org-id="selected.organization"
          :org-key="selected.organization_key"
          :tenant-path="`/ops/alerts/rules?search=${encodeURIComponent(selected.name)}`"
          :related-links="[
            { label: 'Incidents', to: `/platform-ops/alert-center/incidents?org=${encodeURIComponent(selected.organization_key)}` },
            { label: 'Notification Channels', to: `/platform-ops/alert-center/notification-channels?org=${encodeURIComponent(selected.organization_key)}` },
            { label: 'Delivery History', to: `/platform-ops/alert-center/notification-history?org=${encodeURIComponent(selected.organization_key)}` },
          ]"
        />
        <section class="platform-monitoring-drawer__section"><h3>Policy Details</h3><div class="platform-monitoring-drawer__grid">
          <div class="platform-monitoring-drawer__field"><span>Status</span><strong>{{ selected.enabled ? 'Enabled' : 'Disabled' }}</strong></div>
          <div class="platform-monitoring-drawer__field"><span>Severity</span><strong>{{ selected.severity }}</strong></div>
          <div class="platform-monitoring-drawer__field"><span>Type</span><strong>{{ selected.type }}</strong></div>
          <div class="platform-monitoring-drawer__field"><span>Updated</span><strong :class="{ 'hfl-empty-mark': !selected.updated_at }">{{ formatLocalDateTime(selected.updated_at, '—') }}</strong></div>
        </div></section>
        <section class="platform-monitoring-drawer__section"><h3>Description</h3><p class="platform-monitoring-drawer__message">{{ selected.description || 'No description.' }}</p></section>
        <section class="platform-monitoring-drawer__section"><h3>Threshold</h3><pre class="platform-monitoring-drawer__message">{{ JSON.stringify(selected.threshold, null, 2) }}</pre></section>
      </template>
    </el-drawer>
  </ModulePage>
</template>
