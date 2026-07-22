<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CheckCircle2, CircleX, Clock3, RefreshCw, Search, Send } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import HflPagination from '../../../components/HflPagination.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import { useDebouncedAction } from '../../../composables/useDebouncedAction'
import { useResponsiveDrawerWidth } from '../../../composables/useResponsiveDrawerWidth'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import {
  fetchMonitoringDeliveries,
  retryMonitoringDelivery,
  type DeliveryStats,
  type MonitoringDelivery,
} from '../../lib/platformOpsApi'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()
const { drawerSize } = useResponsiveDrawerWidth(3)
const rows = ref<MonitoringDelivery[]>([])
const stats = ref<DeliveryStats>({ total: 0, delivered: 0, failed: 0, pending: 0, delivery_rate: 0 })
const loading = ref(false)
const retrying = ref(false)
const selected = ref<MonitoringDelivery | null>(null)
const drawerOpen = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({
  search: String(route.query.search || ''),
  status: String(route.query.status || ''),
  channel_type: String(route.query.channel_type || ''),
  event_type: String(route.query.event_type || ''),
  org: String(route.query.org || ''),
})
const { schedule: scheduleSearch, runNow: runSearchNow } = useDebouncedAction(applyFilters)

function displayTime(value?: string | null) {
  return formatLocalDateTime(value, '—')
}

function payloadTitle(row: MonitoringDelivery) {
  return String(row.payload?.title || row.payload?.subject || row.event_type || '—')
}

function payloadResource(row: MonitoringDelivery) {
  return String(row.payload?.resource_name || row.payload?.alert_id || row.event_type || '—')
}

async function syncQuery() {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries(filters)) if (value.trim()) query[key] = value.trim()
  await router.replace({ query })
}

async function load() {
  loading.value = true
  try {
    const data = await fetchMonitoringDeliveries({ page: pagination.page, page_size: pagination.pageSize, ...filters })
    rows.value = data.results
    stats.value = data.stats || stats.value
    pagination.count = data.count
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.monitoring.loadFailed')), grouping: true })
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  pagination.page = 1
  void syncQuery()
  void load()
}

function resetFilters() {
  Object.assign(filters, { search: '', status: '', channel_type: '', event_type: '', org: '' })
  runSearchNow()
}

function openDrawer(row: MonitoringDelivery) {
  selected.value = row
  drawerOpen.value = true
}

async function retryDelivery() {
  if (!selected.value || selected.value.status !== 'failed') return
  try {
    await ElMessageBox.confirm(
      t('platformOps.monitoring.confirmRetryDeliveryMessage'),
      t('platformOps.monitoring.confirmRetryDeliveryTitle'),
      { type: 'warning', confirmButtonText: t('platformOps.monitoring.retryDelivery') },
    )
  } catch {
    return
  }
  retrying.value = true
  try {
    await retryMonitoringDelivery(selected.value.id)
    ElMessage.success({ message: t('platformOps.monitoring.retryDeliverySuccess'), grouping: true })
    drawerOpen.value = false
    await load()
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.monitoring.retryDeliveryFailed')), grouping: true })
  } finally {
    retrying.value = false
  }
}

onMounted(load)
watch(() => filters.search, scheduleSearch)
watch(() => [filters.status, filters.channel_type, filters.event_type, filters.org], runSearchNow)
watch(() => [pagination.page, pagination.pageSize], load)
</script>

<template>
  <ModulePage
    :menus="sideNav"
    body-fill
  >
    <div class="platform-monitoring-page">
      <div class="platform-monitoring-page__lead">
        <p class="platform-monitoring-page__subtitle">
          {{ t('platformOps.monitoring.deliveriesSubtitle') }}
        </p><span class="platform-monitoring-page__updated">{{ t('platformOps.monitoring.last24Hours') }}</span>
      </div>
      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard
          :label="t('platformOps.monitoring.totalDeliveries')"
          :value="stats.total"
          accent="indigo"
          accent-side="left"
        >
          <template #icon>
            <Send :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.delivered')"
          :value="stats.delivered"
          accent="green"
          accent-side="left"
        >
          <template #icon>
            <CheckCircle2 :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.failedDeliveries')"
          :value="stats.failed"
          accent="red"
          accent-side="left"
          :pulse="stats.failed > 0"
        >
          <template #icon>
            <CircleX :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.deliveryRate')"
          :value="`${stats.delivery_rate}%`"
          :sub="t('platformOps.monitoring.pendingCount', { count: stats.pending })"
          accent="blue"
          accent-side="left"
        >
          <template #icon>
            <Clock3 :size="16" />
          </template>
        </OpsStatCard>
      </div>
      <HflTablePanel fill>
        <template #toolbar>
          <div class="platform-monitoring-page__filters">
            <el-input
              v-model="filters.search"
              clearable
              class="platform-monitoring-page__search"
              :placeholder="t('platformOps.monitoring.searchDeliveries')"
            >
              <template #prefix>
                <Search :size="15" />
              </template>
            </el-input>
            <el-select
              v-model="filters.status"
              clearable
              class="platform-monitoring-page__filter"
              :aria-label="t('platformOps.monitoring.filterStatus')"
              :placeholder="t('platformOps.monitoring.filterStatus')"
            >
              <el-option
                value="sent"
                label="Delivered"
              /><el-option
                value="failed"
                label="Failed"
              /><el-option
                value="pending"
                label="Pending"
              />
            </el-select>
            <el-select
              v-model="filters.channel_type"
              clearable
              class="platform-monitoring-page__filter"
              :aria-label="t('platformOps.monitoring.filterChannel')"
              :placeholder="t('platformOps.monitoring.filterChannel')"
            >
              <el-option
                value="email"
                label="Email"
              /><el-option
                value="webhook"
                label="Webhook"
              /><el-option
                value="dingtalk"
                label="DingTalk"
              /><el-option
                value="wecom"
                label="WeCom"
              />
            </el-select>
            <el-input
              v-model="filters.event_type"
              clearable
              class="platform-monitoring-page__filter"
              :placeholder="t('platformOps.monitoring.filterEventType')"
            />
            <el-input
              v-model="filters.org"
              clearable
              class="platform-monitoring-page__filter"
              :placeholder="t('platformOps.monitoring.filterAccount')"
            />
            <el-button
              v-if="filters.search || filters.status || filters.channel_type || filters.event_type || filters.org"
              text
              @click="resetFilters"
            >
              {{ t('platformOps.monitoring.resetFilters') }}
            </el-button>
          </div>
        </template>
        <template #toolbar-actions>
          <el-button
            class="hfl-refresh-button"
            :title="t('common.refresh')"
            :aria-label="t('common.refresh')"
            :disabled="loading"
            @click="load"
          >
            <RefreshCw
              :size="16"
              :class="{ 'is-spinning': loading }"
            />
          </el-button>
        </template>
        <template #table="{ tableMaxHeight }">
          <el-table
            v-loading="loading"
            :data="rows"
            stripe
            flexible
            row-key="id"
            class="hfl-list-table"
            :max-height="tableMaxHeight"
          >
            <el-table-column
              :label="t('platformOps.monitoring.colStatus')"
              width="115"
            >
              <template #default="{ row }">
                  <PlatformOpsStatusPill :status="row.status === 'sent' ? 'Delivered' : row.status" />
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.notification')"
              min-width="260"
            >
              <template #default="{ row }">
                <button
                  type="button"
                  class="platform-monitoring-page__title-button"
                  @click="openDrawer(row)"
                >
                  {{ payloadTitle(row) }}
                </button><span class="platform-monitoring-page__cell-meta">{{ payloadResource(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.colChannel')"
              min-width="150"
            >
              <template #default="{ row }">
                {{ row.channel_name }}<span class="platform-monitoring-page__cell-meta">{{ row.channel_type }}</span>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.account')"
              min-width="140"
            >
              <template #default="{ row }">
                <PlatformOpsOrgLink
                  :org-id="row.organization_id"
                  :org-key="row.organization_key"
                />
              </template>
            </el-table-column>
            <el-table-column
              prop="event_type"
              :label="t('platformOps.monitoring.eventType')"
              min-width="170"
            />
            <el-table-column
              :label="t('platformOps.monitoring.lastAttempt')"
              width="170"
            >
              <template #default="{ row }">
                {{ displayTime(row.sent_at || row.created_at) }}
              </template>
            </el-table-column>
            <template #empty>
              <el-empty
                :description="t('platformOps.monitoring.emptyDeliveries')"
                :image-size="72"
              />
            </template>
          </el-table>
        </template>
        <template #footer>
          <HflPagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="pagination.count"
          />
        </template>
      </HflTablePanel>
    </div>

    <el-drawer
      v-model="drawerOpen"
      :size="drawerSize"
      destroy-on-close
    >
      <template #header>
        <div class="platform-monitoring-drawer__header">
          <h2>{{ selected ? payloadTitle(selected) : '' }}</h2><p>{{ selected?.status }} · {{ selected?.channel_type }}</p>
        </div>
      </template>
      <template v-if="selected">
        <div class="platform-monitoring-drawer__actions">
          <el-button
            v-if="selected.status === 'failed'"
            type="primary"
            :loading="retrying"
            @click="retryDelivery"
          >
            {{ t('platformOps.monitoring.retryDelivery') }}
          </el-button>
        </div>
        <section class="platform-monitoring-drawer__section">
          <h3>{{ t('platformOps.monitoring.deliveryDetails') }}</h3><div class="platform-monitoring-drawer__grid">
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.account') }}</span><strong>{{ selected.organization_key }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.colChannel') }}</span><strong>{{ selected.channel_name }} · {{ selected.channel_type }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.eventType') }}</span><strong>{{ selected.event_type }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.lastAttempt') }}</span><strong>{{ displayTime(selected.sent_at || selected.created_at) }}</strong>
            </div>
          </div>
        </section>
        <section
          v-if="selected.error"
          class="platform-monitoring-drawer__section"
        >
          <h3>{{ t('platformOps.monitoring.failureDetails') }}</h3><p class="platform-monitoring-drawer__message">
            {{ selected.error }}
          </p>
        </section>
        <section class="platform-monitoring-drawer__section">
          <h3>{{ t('platformOps.monitoring.payload') }}</h3><p class="platform-monitoring-drawer__message">
            {{ JSON.stringify(selected.payload, null, 2) }}
          </p>
        </section>
      </template>
    </el-drawer>
  </ModulePage>
</template>
