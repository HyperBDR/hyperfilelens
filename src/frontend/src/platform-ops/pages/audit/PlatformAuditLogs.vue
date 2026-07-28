<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Activity, CheckCircle2, CircleX, Clock3, RefreshCw, Search } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import PlatformOpsPagination from '../../components/PlatformOpsPagination.vue'
import { useDebouncedAction } from '../../../composables/useDebouncedAction'
import { useResponsiveDrawerWidth } from '../../../composables/useResponsiveDrawerWidth'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { fetchPlatformAuditLogs, type PlatformAuditLog, type PlatformAuditStats } from '../../lib/platformOpsApi'
import {
  platformAuditActionLabel,
  platformAuditHasDetails,
  platformAuditResultLabel,
  platformAuditTargetSecondary,
  platformAuditTargetTypeLabel,
} from '../../composables/usePlatformAuditPresentation'

const sideNav = usePlatformOpsSideNav()
const { drawerSize } = useResponsiveDrawerWidth(3)
const rows = ref<PlatformAuditLog[]>([])
const stats = ref<PlatformAuditStats>({ total: 0, successful: 0, failed: 0, last_24_hours: 0 })
const loading = ref(false)
const selected = ref<PlatformAuditLog | null>(null)
const drawerOpen = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({ search: '', action: '', result: '', org: '' })
const { schedule: scheduleSearch, runNow: runSearchNow } = useDebouncedAction(applyFilters)

async function load() {
  loading.value = true
  try {
    const data = await fetchPlatformAuditLogs({ page: pagination.page, page_size: pagination.pageSize, ...filters })
    rows.value = data.results
    stats.value = data.stats || stats.value
    pagination.count = data.count
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, 'Failed to load audit logs'), grouping: true })
  } finally { loading.value = false }
}
function applyFilters() { pagination.page = 1; void load() }
function resetFilters() { Object.assign(filters, { search: '', action: '', result: '', org: '' }); runSearchNow() }
function openDrawer(row: PlatformAuditLog) { selected.value = row; drawerOpen.value = true }
onMounted(load)
watch(() => filters.search, scheduleSearch)
watch(() => [filters.action, filters.result, filters.org], runSearchNow)
watch(() => [pagination.page, pagination.pageSize], load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="platform-monitoring-page">
      <div class="platform-monitoring-page__lead"><p class="platform-monitoring-page__subtitle">Review platform administration, access, support, and configuration changes.</p><span class="platform-monitoring-page__updated">Immutable operator history</span></div>
      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard label="Audit Events" :value="stats.total" accent="indigo" accent-side="left"><template #icon><Activity :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Successful" :value="stats.successful" accent="green" accent-side="left"><template #icon><CheckCircle2 :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Failed" :value="stats.failed" accent="red" accent-side="left" :pulse="stats.failed > 0"><template #icon><CircleX :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Last 24 Hours" :value="stats.last_24_hours" accent="blue" accent-side="left"><template #icon><Clock3 :size="16" /></template></OpsStatCard>
      </div>
      <HflTablePanel fill>
        <template #toolbar><div class="platform-monitoring-page__filters">
          <el-input v-model="filters.search" clearable class="platform-monitoring-page__search" placeholder="Search actor, action, or target"><template #prefix><Search :size="15" /></template></el-input>
          <el-input v-model="filters.action" clearable class="platform-monitoring-page__filter" placeholder="Action" />
          <el-select v-model="filters.result" clearable class="platform-monitoring-page__filter" placeholder="Result"><el-option value="success" label="Success" /><el-option value="failure" label="Failed" /></el-select>
          <el-input v-model="filters.org" clearable class="platform-monitoring-page__filter" placeholder="Account key" />
          <el-button v-if="Object.values(filters).some(Boolean)" text @click="resetFilters">Reset</el-button>
        </div></template>
        <template #toolbar-utility><el-button class="hfl-refresh-button" title="Refresh" :disabled="loading" @click="load"><RefreshCw :size="16" :class="{ 'is-spinning': loading }" /></el-button></template>
        <template #table="{ tableMaxHeight }"><el-table v-loading="loading" :data="rows" stripe flexible row-key="id" class="hfl-list-table" :max-height="tableMaxHeight">
          <el-table-column label="Time" width="175"><template #default="{ row }">{{ formatLocalDateTime(row.created_at, '—') }}</template></el-table-column>
          <el-table-column label="Actor" min-width="190"><template #default="{ row }">{{ row.actor_email || 'System' }}<span class="platform-monitoring-page__cell-meta">{{ row.ip_address || 'No IP recorded' }}</span></template></el-table-column>
          <el-table-column label="Action" min-width="240"><template #default="{ row }"><button type="button" class="platform-monitoring-page__title-button" @click="openDrawer(row)">{{ platformAuditActionLabel(row.action) }}</button><span class="platform-monitoring-page__cell-meta">{{ row.action }}</span></template></el-table-column>
          <el-table-column label="Target" min-width="190"><template #default="{ row }">{{ platformAuditTargetTypeLabel(row.target_type) }}<span class="platform-monitoring-page__cell-meta">{{ platformAuditTargetSecondary(row) }}</span></template></el-table-column>
          <el-table-column prop="org_key" label="Account" width="145" />
          <el-table-column label="Result" width="130"><template #default="{ row }"><PlatformOpsStatusPill :status="platformAuditResultLabel(row.result)" /></template></el-table-column>
          <template #empty><el-empty description="No audit events found" :image-size="72" /></template>
        </el-table></template>
        <template #footer><PlatformOpsPagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" :total="pagination.count" /></template>
      </HflTablePanel>
    </div>
    <el-drawer v-model="drawerOpen" :size="drawerSize" destroy-on-close><template #header><div class="platform-monitoring-drawer__header"><h2>{{ platformAuditActionLabel(selected?.action) }}</h2><p>{{ selected?.actor_email || 'System' }} · {{ platformAuditResultLabel(selected?.result) }}</p></div></template><template v-if="selected"><section class="platform-monitoring-drawer__section"><h3>Audit Context</h3><div class="platform-monitoring-drawer__grid"><div class="platform-monitoring-drawer__field"><span>Time</span><strong>{{ formatLocalDateTime(selected.created_at, '—') }}</strong></div><div class="platform-monitoring-drawer__field"><span>IP Address</span><strong>{{ selected.ip_address || '—' }}</strong></div><div class="platform-monitoring-drawer__field"><span>Target Type</span><strong>{{ platformAuditTargetTypeLabel(selected.target_type) }}</strong></div><div class="platform-monitoring-drawer__field"><span>Target ID</span><strong>{{ selected.target_id || '—' }}</strong></div><div class="platform-monitoring-drawer__field"><span>Account</span><strong>{{ selected.org_key || 'Platform' }}</strong></div><div class="platform-monitoring-drawer__field"><span>Machine Action</span><strong>{{ selected.action }}</strong></div></div></section><section class="platform-monitoring-drawer__section"><h3>Details</h3><p v-if="!platformAuditHasDetails(selected.details)" class="platform-monitoring-drawer__empty-details">No additional context was recorded for this event.</p><el-collapse v-else><el-collapse-item title="Raw event details" name="raw"><pre class="platform-monitoring-drawer__message">{{ JSON.stringify(selected.details, null, 2) }}</pre></el-collapse-item></el-collapse></section></template></el-drawer>
  </ModulePage>
</template>

<style scoped>
.platform-monitoring-drawer__empty-details {
  margin: 0;
  padding: 14px 16px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
  line-height: 1.5;
}
</style>
