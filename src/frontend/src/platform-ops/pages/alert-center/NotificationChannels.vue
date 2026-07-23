<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { BellRing, CircleCheck, CircleOff, RefreshCw, Search, Send } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import HflPagination from '../../../components/HflPagination.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import { useDebouncedAction } from '../../../composables/useDebouncedAction'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { fetchPlatformNotificationChannels, type NotificationChannelStats, type PlatformNotificationChannel } from '../../lib/platformOpsApi'

const sideNav = usePlatformOpsSideNav()
const rows = ref<PlatformNotificationChannel[]>([])
const stats = ref<NotificationChannelStats>({ total: 0, active: 0, inactive: 0, types: 0 })
const loading = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({ search: '', type: '', active: '', org: '' })
const { schedule: scheduleSearch, runNow: runSearchNow } = useDebouncedAction(applyFilters)

async function load() {
  loading.value = true
  try {
    const data = await fetchPlatformNotificationChannels({ page: pagination.page, page_size: pagination.pageSize, ...filters })
    rows.value = data.results
    stats.value = data.stats || stats.value
    pagination.count = data.count
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, 'Failed to load notification channels'), grouping: true })
  } finally {
    loading.value = false
  }
}
function applyFilters() { pagination.page = 1; void load() }
function resetFilters() { Object.assign(filters, { search: '', type: '', active: '', org: '' }); runSearchNow() }
onMounted(load)
watch(() => filters.search, scheduleSearch)
watch(() => [filters.type, filters.active, filters.org], runSearchNow)
watch(() => [pagination.page, pagination.pageSize], load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="platform-monitoring-page">
      <div class="platform-monitoring-page__lead"><p class="platform-monitoring-page__subtitle">Review notification destinations configured across customer accounts.</p><span class="platform-monitoring-page__updated">Read-only inventory</span></div>
      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard label="Total Channels" :value="stats.total" accent="indigo" accent-side="left"><template #icon><BellRing :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Active" :value="stats.active" accent="green" accent-side="left"><template #icon><CircleCheck :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Inactive" :value="stats.inactive" accent="orange" accent-side="left"><template #icon><CircleOff :size="16" /></template></OpsStatCard>
        <OpsStatCard label="Channel Types" :value="stats.types" accent="blue" accent-side="left"><template #icon><Send :size="16" /></template></OpsStatCard>
      </div>
      <HflTablePanel fill>
      <template #toolbar><div class="platform-monitoring-page__filters">
          <el-input v-model="filters.search" clearable class="platform-monitoring-page__search" placeholder="Search channels or accounts"><template #prefix><Search :size="15" /></template></el-input>
          <el-select v-model="filters.type" clearable class="platform-monitoring-page__filter" placeholder="Channel type"><el-option value="email" label="Email" /><el-option value="webhook" label="Webhook" /><el-option value="dingtalk" label="DingTalk" /><el-option value="wecom" label="WeCom" /><el-option value="feishu" label="Feishu" /></el-select>
          <el-select v-model="filters.active" clearable class="platform-monitoring-page__filter" placeholder="Status"><el-option value="true" label="Active" /><el-option value="false" label="Inactive" /></el-select>
          <el-input v-model="filters.org" clearable class="platform-monitoring-page__filter" placeholder="Account key" />
          <el-button v-if="Object.values(filters).some(Boolean)" text @click="resetFilters">Reset</el-button>
        </div></template>
      <template #toolbar-utility><el-button class="hfl-refresh-button" title="Refresh" :disabled="loading" @click="load"><RefreshCw :size="16" :class="{ 'is-spinning': loading }" /></el-button></template>
        <template #table="{ tableMaxHeight }"><el-table v-loading="loading" :data="rows" stripe flexible row-key="id" class="hfl-list-table" :max-height="tableMaxHeight">
          <el-table-column prop="name" label="Channel" min-width="230" />
          <el-table-column label="Status" width="110"><template #default="{ row }"><PlatformOpsStatusPill :status="row.is_active ? 'Active' : 'Inactive'" /></template></el-table-column>
          <el-table-column prop="channel_type" label="Type" width="140" />
          <el-table-column label="Account" min-width="170"><template #default="{ row }"><PlatformOpsOrgLink :org-id="row.organization_id" :org-key="row.organization_key" /></template></el-table-column>
          <el-table-column prop="delivery_count" label="Deliveries" width="120" />
          <el-table-column label="Updated" width="170"><template #default="{ row }">{{ formatLocalDateTime(row.updated_at, '—') }}</template></el-table-column>
          <template #empty><el-empty description="No notification channels found" :image-size="72" /></template>
        </el-table></template>
        <template #footer><HflPagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" :total="pagination.count" /></template>
      </HflTablePanel>
    </div>
  </ModulePage>
</template>
