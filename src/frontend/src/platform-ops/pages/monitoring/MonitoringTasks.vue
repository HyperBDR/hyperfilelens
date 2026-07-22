<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Activity, CircleCheck, CircleX, Clock3, RefreshCw, Search } from 'lucide-vue-next'
import DangerConfirmDialog, { type DangerConfirmItem } from '../../../components/DangerConfirmDialog.vue'
import ModulePage from '../../../components/ModulePage.vue'
import HflPagination from '../../../components/HflPagination.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import TaskTypeLabel from '../../../components/TaskTypeLabel.vue'
import { useDebouncedAction } from '../../../composables/useDebouncedAction'
import { useResponsiveDrawerWidth } from '../../../composables/useResponsiveDrawerWidth'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import {
  fetchMonitoringTasks,
  runMonitoringTaskAction,
  type MonitoringTask,
  type TaskStats,
} from '../../lib/platformOpsApi'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()
const { drawerSize } = useResponsiveDrawerWidth(3)
const rows = ref<MonitoringTask[]>([])
const stats = ref<TaskStats>({ total: 0, running: 0, failed: 0, timeout: 0, success_rate: 0 })
const busy = ref(false)
const actionLoading = ref(false)
const selected = ref<MonitoringTask | null>(null)
const drawerOpen = ref(false)
const actionConfirmOpen = ref(false)
const pendingAction = ref<'cancel' | 'retry' | null>(null)
const pendingTask = ref<MonitoringTask | null>(null)
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({
  search: String(route.query.search || ''),
  status: String(route.query.status || ''),
  task_type: String(route.query.task_type || ''),
  org: String(route.query.org || ''),
})
const { schedule: scheduleSearch, runNow: runSearchNow } = useDebouncedAction(applyFilters)
const canCancel = computed(() => selected.value?.status === 'pending' || selected.value?.status === 'running')
const canRetry = computed(() => ['failed', 'timeout', 'cancelled'].includes(selected.value?.status || ''))
const actionConfirmTitle = computed(() => t(
  `platformOps.monitoring.confirmTask${pendingAction.value === 'cancel' ? 'Cancel' : 'Retry'}Title`,
))
const actionConfirmMessage = computed(() => t(
  `platformOps.monitoring.confirmTask${pendingAction.value === 'cancel' ? 'Cancel' : 'Retry'}Message`,
))
const actionConfirmText = computed(() => t(
  `platformOps.monitoring.${pendingAction.value === 'cancel' ? 'cancel' : 'retry'}Task`,
))
const actionConfirmItems = computed<DangerConfirmItem[]>(() => (
  pendingTask.value
    ? [{
        key: pendingTask.value.task_uuid,
        name: pendingTask.value.display_name,
        description: pendingTask.value.organization_key,
        status: { label: pendingTask.value.status, tone: pendingAction.value === 'cancel' ? 'danger' : 'info' },
      }]
    : []
))

function displayTime(value?: string | null) {
  return formatLocalDateTime(value, '—')
}

function duration(row: MonitoringTask) {
  if (!row.started_at) return '—'
  const end = row.finished_at ? new Date(row.finished_at).getTime() : Date.now()
  const seconds = Math.max(0, Math.floor((end - new Date(row.started_at).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  return minutes < 60 ? `${minutes}m ${seconds % 60}s` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

async function syncQuery() {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries(filters)) if (value.trim()) query[key] = value.trim()
  await router.replace({ query })
}

async function load() {
  busy.value = true
  try {
    const data = await fetchMonitoringTasks({ page: pagination.page, page_size: pagination.pageSize, ...filters })
    rows.value = data.results
    stats.value = data.stats || stats.value
    pagination.count = data.count
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.monitoring.loadFailed')), grouping: true })
  } finally {
    busy.value = false
  }
}

function applyFilters() {
  pagination.page = 1
  void syncQuery()
  void load()
}

function resetFilters() {
  Object.assign(filters, { search: '', status: '', task_type: '', org: '' })
  runSearchNow()
}

function openDrawer(row: MonitoringTask) {
  selected.value = row
  drawerOpen.value = true
}

function requestAction(action: 'cancel' | 'retry') {
  if (!selected.value) return
  pendingAction.value = action
  pendingTask.value = selected.value
  actionConfirmOpen.value = true
}

function cancelAction() {
  if (actionLoading.value) return
  pendingAction.value = null
  pendingTask.value = null
}

async function performAction() {
  const action = pendingAction.value
  const task = pendingTask.value
  if (!action || !task) return
  actionLoading.value = true
  try {
    await runMonitoringTaskAction(task.task_uuid, action)
    ElMessage.success({ message: t(`platformOps.monitoring.${action}TaskSuccess`), grouping: true })
    actionConfirmOpen.value = false
    pendingAction.value = null
    pendingTask.value = null
    drawerOpen.value = false
    await load()
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.monitoring.actionFailed')), grouping: true })
  } finally {
    actionLoading.value = false
  }
}

onMounted(load)
watch(() => filters.search, scheduleSearch)
watch(() => [filters.status, filters.task_type, filters.org], runSearchNow)
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
          {{ t('platformOps.monitoring.tasksSubtitle') }}
        </p>
        <span class="platform-monitoring-page__updated">{{ t('platformOps.monitoring.last24Hours') }}</span>
      </div>
      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard
          :label="t('platformOps.monitoring.runningTasks')"
          :value="stats.running"
          accent="blue"
          accent-side="left"
          :pulse="stats.running > 0"
        >
          <template #icon>
            <Activity :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.failedTasks')"
          :value="stats.failed"
          :sub="t('platformOps.monitoring.last24Hours')"
          accent="red"
          accent-side="left"
        >
          <template #icon>
            <CircleX :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.timedOutTasks')"
          :value="stats.timeout"
          :sub="t('platformOps.monitoring.last24Hours')"
          accent="orange"
          accent-side="left"
        >
          <template #icon>
            <Clock3 :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.taskSuccessRate')"
          :value="`${stats.success_rate}%`"
          :sub="t('platformOps.monitoring.last24Hours')"
          accent="green"
          accent-side="left"
        >
          <template #icon>
            <CircleCheck :size="16" />
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
              :placeholder="t('platformOps.monitoring.searchTasks')"
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
                v-for="status in ['pending', 'running', 'success', 'failed', 'timeout', 'cancelled']"
                :key="status"
                :value="status"
                :label="status"
              />
            </el-select>
            <el-select
              v-model="filters.task_type"
              clearable
              class="platform-monitoring-page__filter"
              :aria-label="t('platformOps.monitoring.filterTaskType')"
              :placeholder="t('platformOps.monitoring.filterTaskType')"
            >
              <el-option
                v-for="type in ['backup', 'restore', 'snapshot_download', 'snapshot_delete', 'repository_operation']"
                :key="type"
                :value="type"
                :label="type"
              />
            </el-select>
            <el-input
              v-model="filters.org"
              clearable
              class="platform-monitoring-page__filter"
              :placeholder="t('platformOps.monitoring.filterAccount')"
            />
            <el-button
              v-if="filters.search || filters.status || filters.task_type || filters.org"
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
            :disabled="busy"
            @click="load"
          >
            <RefreshCw
              :size="16"
              :class="{ 'is-spinning': busy }"
            />
          </el-button>
        </template>
        <template #table="{ tableMaxHeight }">
          <el-table
            v-loading="busy"
            :data="rows"
            stripe
            flexible
            row-key="id"
            class="hfl-list-table"
            :max-height="tableMaxHeight"
          >
            <el-table-column
              :label="t('platformOps.monitoring.colTask')"
              min-width="260"
            >
              <template #default="{ row }">
                <button
                  type="button"
                  class="platform-monitoring-page__title-button"
                  @click="openDrawer(row)"
                >
                  {{ row.display_name }}
                </button><span class="platform-monitoring-page__cell-meta">{{ row.current_step || row.task_uuid }}</span>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.colTaskType')"
              min-width="150"
            >
              <template #default="{ row }">
                <TaskTypeLabel :type="row.task_type" />
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.colStatus')"
              width="120"
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
              :label="t('platformOps.monitoring.progress')"
              width="145"
            >
              <template #default="{ row }">
                <div class="platform-monitoring-page__progress">
                  <el-progress
                    :percentage="Number(row.progress || 0)"
                    :show-text="false"
                    :stroke-width="6"
                  /><span>{{ Number(row.progress || 0) }}%</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.duration')"
              width="100"
            >
              <template #default="{ row }">
                {{ duration(row) }}
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.colFinished')"
              width="170"
            >
              <template #default="{ row }">
                {{ displayTime(row.finished_at || row.created_at) }}
              </template>
            </el-table-column>
            <template #empty>
              <el-empty
                :description="t('platformOps.monitoring.emptyTasks')"
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
          <h2>{{ selected?.display_name }}</h2><p>{{ selected?.status }} · {{ selected?.task_uuid }}</p>
        </div>
      </template>
      <template v-if="selected">
        <div class="platform-monitoring-drawer__actions">
          <el-button
            v-if="canCancel"
            type="danger"
            plain
            :loading="actionLoading"
            @click="requestAction('cancel')"
          >
            {{ t('platformOps.monitoring.cancelTask') }}
          </el-button><el-button
            v-if="canRetry"
            type="primary"
            :loading="actionLoading"
            @click="requestAction('retry')"
          >
            {{ t('platformOps.monitoring.retryTask') }}
          </el-button>
        </div>
        <section class="platform-monitoring-drawer__section">
          <h3>{{ t('platformOps.monitoring.taskDetails') }}</h3><div class="platform-monitoring-drawer__grid">
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.account') }}</span><strong>{{ selected.organization_key }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.colTaskType') }}</span><strong>{{ selected.task_type }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.started') }}</span><strong>{{ displayTime(selected.started_at) }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.finished') }}</span><strong>{{ displayTime(selected.finished_at) }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.duration') }}</span><strong>{{ duration(selected) }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.retryCount') }}</span><strong>{{ selected.retry_count }}</strong>
            </div>
          </div>
        </section>
        <section
          v-if="selected.error_message"
          class="platform-monitoring-drawer__section"
        >
          <h3>{{ t('platformOps.monitoring.errorDetails') }}</h3><p class="platform-monitoring-drawer__message">
            {{ selected.error_code ? `${selected.error_code}: ` : '' }}{{ selected.error_message }}
          </p>
        </section>
      </template>
    </el-drawer>
    <DangerConfirmDialog
      v-model="actionConfirmOpen"
      :title="actionConfirmTitle"
      :message="actionConfirmMessage"
      :items="actionConfirmItems"
      :level="pendingAction === 'cancel' ? 'high' : 'low'"
      :cancel-text="t('common.cancel')"
      :confirm-text="actionConfirmText"
      :loading="actionLoading"
      @confirm="performAction"
      @cancel="cancelAction"
    />
  </ModulePage>
</template>
