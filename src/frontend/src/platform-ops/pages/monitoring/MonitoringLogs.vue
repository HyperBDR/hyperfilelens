<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { AlertTriangle, CircleX, Layers3, RefreshCw, ScrollText, Search } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import HflPagination from '../../../components/HflPagination.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import { useDebouncedAction } from '../../../composables/useDebouncedAction'
import { useResponsiveDrawerWidth } from '../../../composables/useResponsiveDrawerWidth'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { fetchPlatformLogs, type PlatformLogRow, type PlatformLogStats } from '../../lib/platformOpsApi'

const sideNav = usePlatformOpsSideNav()
const { drawerSize } = useResponsiveDrawerWidth(3)
const rows = ref<PlatformLogRow[]>([])
const stats = ref<PlatformLogStats>({ total: 0, errors: 0, warnings: 0, services: 0 })
const serviceOptions = ref<string[]>([])
const loading = ref(false)
const selected = ref<PlatformLogRow | null>(null)
const drawerOpen = ref(false)
const pagination = reactive({ page: 1, pageSize: 50, count: 0 })
const filters = reactive({ search: '', level: '', service: '' })
const { schedule: scheduleSearch, runNow: runSearchNow } = useDebouncedAction(applyFilters)

async function load() {
  loading.value = true
  try {
    const data = await fetchPlatformLogs({ page: pagination.page, page_size: pagination.pageSize, ...filters })
    rows.value = data.results
    stats.value = data.stats || stats.value
    serviceOptions.value = data.service_options || []
    pagination.count = data.count
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, 'Failed to load platform logs'), grouping: true })
  } finally { loading.value = false }
}
function applyFilters() { pagination.page = 1; void load() }
function resetFilters() { Object.assign(filters, { search: '', level: '', service: '' }); runSearchNow() }
function openDrawer(row: PlatformLogRow) { selected.value = row; drawerOpen.value = true }
onMounted(load)
watch(() => filters.search, scheduleSearch)
watch(() => [filters.level, filters.service], runSearchNow)
watch(() => [pagination.page, pagination.pageSize], load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="platform-monitoring-page">
      <div class="platform-monitoring-page__lead"><p class="platform-monitoring-page__subtitle">Search recent deployment logs. Sensitive credential values are redacted before delivery.</p><span class="platform-monitoring-page__updated">Up to 2,000 lines per service</span></div>
      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard label="Log Events" :value="stats.total" accent="indigo" accent-side="left"><template #icon><ScrollText :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Errors" :value="stats.errors" accent="red" accent-side="left" :pulse="stats.errors > 0"><template #icon><CircleX :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Warnings" :value="stats.warnings" accent="orange" accent-side="left"><template #icon><AlertTriangle :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Services" :value="stats.services" accent="blue" accent-side="left"><template #icon><Layers3 :size="16" /></template></OpsStatCard>
      </div>
      <HflTablePanel fill>
        <template #toolbar><div class="platform-monitoring-page__filters">
          <el-input v-model="filters.search" clearable class="platform-monitoring-page__search" placeholder="Search messages or services"><template #prefix><Search :size="15" /></template></el-input>
          <el-select v-model="filters.level" clearable class="platform-monitoring-page__filter" placeholder="Level"><el-option value="DEBUG" label="Debug" /><el-option value="INFO" label="Info" /><el-option value="WARNING" label="Warning" /><el-option value="ERROR" label="Error" /><el-option value="CRITICAL" label="Critical" /></el-select>
          <el-select v-model="filters.service" clearable filterable class="platform-monitoring-page__filter" placeholder="Service"><el-option v-for="service in serviceOptions" :key="service" :value="service" :label="service" /></el-select>
          <el-button v-if="Object.values(filters).some(Boolean)" text @click="resetFilters">Reset</el-button>
        </div></template>
        <template #toolbar-actions><el-button class="hfl-refresh-button" title="Refresh" :disabled="loading" @click="load"><RefreshCw :size="16" :class="{ 'is-spinning': loading }" /></el-button></template>
        <template #table="{ tableMaxHeight }"><el-table v-loading="loading" :data="rows" stripe flexible row-key="id" class="hfl-list-table platform-log-table" :max-height="tableMaxHeight">
          <el-table-column label="Time" width="185"><template #default="{ row }">{{ row.timestamp ? formatLocalDateTime(row.timestamp, row.timestamp) : '—' }}</template></el-table-column>
          <el-table-column label="Level" width="115"><template #default="{ row }"><PlatformOpsStatusPill :status="row.level" /></template></el-table-column>
          <el-table-column prop="service" label="Service" width="160" />
          <el-table-column label="Message" min-width="420"><template #default="{ row }"><button type="button" class="platform-monitoring-page__title-button platform-log-table__message" @click="openDrawer(row)">{{ row.message }}</button></template></el-table-column>
          <template #empty><el-empty description="No log events found" :image-size="72" /></template>
        </el-table></template>
        <template #footer><HflPagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" :total="pagination.count" /></template>
      </HflTablePanel>
    </div>
    <el-drawer v-model="drawerOpen" :size="drawerSize" destroy-on-close><template #header><div class="platform-monitoring-drawer__header"><h2>Log Event</h2><p>{{ selected?.service }} · {{ selected?.level }}</p></div></template><template v-if="selected"><section class="platform-monitoring-drawer__section"><h3>Event Details</h3><div class="platform-monitoring-drawer__grid"><div class="platform-monitoring-drawer__field"><span>Time</span><strong>{{ selected.timestamp || '—' }}</strong></div><div class="platform-monitoring-drawer__field"><span>Service</span><strong>{{ selected.service }}</strong></div></div></section><section class="platform-monitoring-drawer__section"><h3>Message</h3><pre class="platform-monitoring-drawer__message">{{ selected.message }}</pre></section></template></el-drawer>
  </ModulePage>
</template>
