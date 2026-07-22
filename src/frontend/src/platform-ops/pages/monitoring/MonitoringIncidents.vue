<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { AlertTriangle, CheckCircle2, CircleAlert, RefreshCw, Search, ShieldCheck } from 'lucide-vue-next'
import DangerConfirmDialog, { type DangerConfirmItem } from '../../../components/DangerConfirmDialog.vue'
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
  fetchMonitoringIncidents,
  runMonitoringIncidentAction,
  type IncidentStats,
  type MonitoringIncident,
} from '../../lib/platformOpsApi'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()
const { drawerSize } = useResponsiveDrawerWidth(3)

const rows = ref<MonitoringIncident[]>([])
const stats = ref<IncidentStats>({ total: 0, firing: 0, critical: 0, acknowledged: 0, resolved: 0 })
const loading = ref(false)
const actionLoading = ref(false)
const selected = ref<MonitoringIncident | null>(null)
const drawerOpen = ref(false)
const selectedRows = ref<MonitoringIncident[]>([])
const resolveConfirmOpen = ref(false)
const pendingResolveTargets = ref<MonitoringIncident[]>([])
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({
  search: String(route.query.search || ''),
  status: String(route.query.status || ''),
  severity: String(route.query.severity || ''),
  org: String(route.query.org || ''),
})
const { schedule: scheduleSearch, runNow: runSearchNow } = useDebouncedAction(applyFilters)

const canAcknowledge = computed(() => selectedRows.value.some((row) => row.status === 'firing'))
const canResolve = computed(() => selectedRows.value.some((row) => row.status !== 'resolved'))
const resolveConfirmItems = computed<DangerConfirmItem[]>(() => pendingResolveTargets.value.map((row) => ({
  key: row.id,
  name: row.title,
  description: `${row.organization_key} · ${resourceLabel(row)}`,
  status: { label: row.status, tone: 'warning' },
})))

function severityClass(value: string) {
  if (value === 'critical') return 'hfl-ops-severity-pill--critical'
  if (value === 'warning') return 'hfl-ops-severity-pill--warning'
  if (value === 'info') return 'hfl-ops-severity-pill--info'
  return 'hfl-ops-severity-pill--neutral'
}

function displayTime(value?: string | null) {
  return formatLocalDateTime(value, '—')
}

function resourceLabel(row: MonitoringIncident) {
  const value = row.resource_name || row.resource_type || '—'
  return row.resource_type && row.resource_name ? `${value} · ${row.resource_type}` : value
}

async function syncQuery() {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries(filters)) {
    if (value.trim()) query[key] = value.trim()
  }
  await router.replace({ query })
}

async function load() {
  loading.value = true
  try {
    const data = await fetchMonitoringIncidents({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters,
    })
    rows.value = data.results
    stats.value = data.stats || stats.value
    pagination.count = data.count
    selectedRows.value = []
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
  filters.search = ''
  filters.status = ''
  filters.severity = ''
  filters.org = ''
  runSearchNow()
}

function openDrawer(row: MonitoringIncident) {
  selected.value = row
  drawerOpen.value = true
}

async function executeAction(action: 'acknowledge' | 'resolve', targets: MonitoringIncident[]) {
  const validTargets = targets.filter((row) => (
    action === 'acknowledge' ? row.status === 'firing' : row.status !== 'resolved'
  ))
  if (!validTargets.length) return
  actionLoading.value = true
  try {
    const settled = await Promise.allSettled(
      validTargets.map((row) => runMonitoringIncidentAction(row.id, action)),
    )
    const failed = settled.filter((result) => result.status === 'rejected').length
    if (failed) {
      ElMessage.warning({ message: t('platformOps.monitoring.partialAction', { failed }), grouping: true })
    } else {
      ElMessage.success({ message: t(`platformOps.monitoring.${action}Success`), grouping: true })
    }
    drawerOpen.value = false
    await load()
  } finally {
    actionLoading.value = false
  }
}

async function performAction(action: 'acknowledge' | 'resolve', targets: MonitoringIncident[]) {
  const validTargets = targets.filter((row) => (
    action === 'acknowledge' ? row.status === 'firing' : row.status !== 'resolved'
  ))
  if (!validTargets.length) return
  if (action === 'resolve') {
    pendingResolveTargets.value = validTargets
    resolveConfirmOpen.value = true
    return
  }
  await executeAction(action, validTargets)
}

function cancelResolve() {
  if (actionLoading.value) return
  pendingResolveTargets.value = []
}

async function confirmResolve() {
  await executeAction('resolve', pendingResolveTargets.value)
  resolveConfirmOpen.value = false
  cancelResolve()
}

onMounted(load)
watch(() => filters.search, scheduleSearch)
watch(() => [filters.status, filters.severity, filters.org], runSearchNow)
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
          {{ t('platformOps.monitoring.incidentsSubtitle') }}
        </p>
        <span class="platform-monitoring-page__updated">{{ t('platformOps.monitoring.last24Hours') }}</span>
      </div>

      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard
          :label="t('platformOps.monitoring.firingIncidents')"
          :value="stats.firing"
          accent="red"
          accent-side="left"
          :pulse="stats.firing > 0"
        >
          <template #icon>
            <CircleAlert :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.criticalIncidents')"
          :value="stats.critical"
          accent="orange"
          accent-side="left"
        >
          <template #icon>
            <AlertTriangle :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.acknowledgedIncidents')"
          :value="stats.acknowledged"
          accent="blue"
          accent-side="left"
        >
          <template #icon>
            <ShieldCheck :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.resolvedIncidents')"
          :value="stats.resolved"
          :sub="t('platformOps.monitoring.last24Hours')"
          accent="green"
          accent-side="left"
        >
          <template #icon>
            <CheckCircle2 :size="16" />
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
              :placeholder="t('platformOps.monitoring.searchIncidents')"
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
                value="firing"
                label="Firing"
              />
              <el-option
                value="acknowledged"
                label="Acknowledged"
              />
              <el-option
                value="resolved"
                label="Resolved"
              />
            </el-select>
            <el-select
              v-model="filters.severity"
              clearable
              class="platform-monitoring-page__filter"
              :aria-label="t('platformOps.monitoring.filterSeverity')"
              :placeholder="t('platformOps.monitoring.filterSeverity')"
            >
              <el-option
                value="critical"
                label="Critical"
              />
              <el-option
                value="warning"
                label="Warning"
              />
              <el-option
                value="info"
                label="Info"
              />
            </el-select>
            <el-input
              v-model="filters.org"
              clearable
              class="platform-monitoring-page__filter"
              :placeholder="t('platformOps.monitoring.filterAccount')"
            />
            <el-button
              v-if="filters.search || filters.status || filters.severity || filters.org"
              text
              @click="resetFilters"
            >
              {{ t('platformOps.monitoring.resetFilters') }}
            </el-button>
          </div>
        </template>
        <template #toolbar-actions>
          <el-button
            :disabled="!canAcknowledge || actionLoading"
            @click="performAction('acknowledge', selectedRows)"
          >
            {{ t('platformOps.monitoring.acknowledge') }}
          </el-button>
          <el-button
            :disabled="!canResolve || actionLoading"
            @click="performAction('resolve', selectedRows)"
          >
            {{ t('platformOps.monitoring.resolve') }}
          </el-button>
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
            @selection-change="selectedRows = $event"
          >
            <el-table-column
              type="selection"
              width="44"
            />
            <el-table-column
              :label="t('platformOps.monitoring.colSeverity')"
              width="104"
            >
              <template #default="{ row }">
                <span
                  class="hfl-ops-severity-pill"
                  :class="severityClass(row.severity)"
                >{{ row.severity }}</span>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.incident')"
              min-width="250"
            >
              <template #default="{ row }">
                <button
                  class="platform-monitoring-page__title-button"
                  type="button"
                  @click="openDrawer(row)"
                >
                  {{ row.title }}
                </button>
                <span class="platform-monitoring-page__cell-meta">{{ resourceLabel(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.colStatus')"
              width="130"
            >
              <template #default="{ row }">
                <PlatformOpsStatusPill :status="row.status" />
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
              :label="t('platformOps.monitoring.colLastTriggered')"
              width="170"
            >
              <template #default="{ row }">
                {{ displayTime(row.last_triggered_at || row.created_at) }}
              </template>
            </el-table-column>
            <template #empty>
              <el-empty
                :description="t('platformOps.monitoring.emptyIncidents')"
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
          <h2>{{ selected?.title }}</h2><p>{{ selected?.severity }} · {{ selected?.status }}</p>
        </div>
      </template>
      <template v-if="selected">
        <div class="platform-monitoring-drawer__actions">
          <el-button
            v-if="selected.status === 'firing'"
            :loading="actionLoading"
            @click="performAction('acknowledge', [selected])"
          >
            {{ t('platformOps.monitoring.acknowledge') }}
          </el-button>
          <el-button
            v-if="selected.status !== 'resolved'"
            type="primary"
            :loading="actionLoading"
            @click="performAction('resolve', [selected])"
          >
            {{ t('platformOps.monitoring.resolve') }}
          </el-button>
        </div>
        <section class="platform-monitoring-drawer__section">
          <h3>{{ t('platformOps.monitoring.incidentDetails') }}</h3>
          <div class="platform-monitoring-drawer__grid">
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.account') }}</span><strong>{{ selected.organization_key }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.colStatus') }}</span><strong>{{ selected.status }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.resource') }}</span><strong>{{ resourceLabel(selected) }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.occurrences') }}</span><strong>{{ selected.metadata?.occurrences || '—' }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.firstTriggered') }}</span><strong>{{ displayTime(selected.first_triggered_at || selected.created_at) }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.lastTriggered') }}</span><strong>{{ displayTime(selected.last_triggered_at) }}</strong>
            </div>
          </div>
        </section>
        <section class="platform-monitoring-drawer__section">
          <h3>{{ t('platformOps.monitoring.description') }}</h3><p class="platform-monitoring-drawer__message">
            {{ selected.message || '—' }}
          </p>
        </section>
      </template>
    </el-drawer>
    <DangerConfirmDialog
      v-model="resolveConfirmOpen"
      :title="t('platformOps.monitoring.confirmResolveTitle')"
      :message="t('platformOps.monitoring.confirmResolveMessage', { count: pendingResolveTargets.length })"
      :items="resolveConfirmItems"
      level="high"
      :cancel-text="t('common.cancel')"
      :confirm-text="t('platformOps.monitoring.resolve')"
      :loading="actionLoading"
      @confirm="confirmResolve"
      @cancel="cancelResolve"
    />
  </ModulePage>
</template>
