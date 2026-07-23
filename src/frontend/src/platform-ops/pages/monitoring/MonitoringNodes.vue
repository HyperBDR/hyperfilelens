<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { CircleCheck, CircleX, RefreshCw, Search, Server, ShieldAlert } from 'lucide-vue-next'
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
import { fetchMonitoringNodes, type MonitoringNode, type NodeStats } from '../../lib/platformOpsApi'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()
const { drawerSize } = useResponsiveDrawerWidth(3)
const rows = ref<MonitoringNode[]>([])
const stats = ref<NodeStats>({ total: 0, online: 0, offline: 0, outdated: 0, latest_version: '' })
const busy = ref(false)
const selected = ref<MonitoringNode | null>(null)
const drawerOpen = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({
  search: String(route.query.search || ''),
  status: String(route.query.status || ''),
  role: String(route.query.role || ''),
  org: String(route.query.org || ''),
})
const { schedule: scheduleSearch, runNow: runSearchNow } = useDebouncedAction(applyFilters)

function displayTime(value?: string | null) {
  return formatLocalDateTime(value, '—')
}

function isOutdated(row: MonitoringNode) {
  return row.is_outdated
}

function metadataValue(key: string) {
  const value = selected.value?.metadata?.[key]
  return value === undefined || value === null || value === '' ? '—' : String(value)
}

async function syncQuery() {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries(filters)) if (value.trim()) query[key] = value.trim()
  await router.replace({ query })
}

async function load() {
  busy.value = true
  try {
    const data = await fetchMonitoringNodes({ page: pagination.page, page_size: pagination.pageSize, ...filters })
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
  Object.assign(filters, { search: '', status: '', role: '', org: '' })
  runSearchNow()
}

function openDrawer(row: MonitoringNode) {
  selected.value = row
  drawerOpen.value = true
}

onMounted(load)
watch(() => filters.search, scheduleSearch)
watch(() => [filters.status, filters.role, filters.org], runSearchNow)
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
          {{ t('platformOps.monitoring.nodesSubtitle') }}
        </p><span class="platform-monitoring-page__updated">{{ t('platformOps.monitoring.latestAgent', { version: stats.latest_version || '—' }) }}</span>
      </div>
      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard
          :label="t('platformOps.monitoring.totalNodes')"
          :value="stats.total"
          accent="indigo"
          accent-side="left"
        >
          <template #icon>
            <Server :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.onlineNodes')"
          :value="stats.online"
          accent="green"
          accent-side="left"
        >
          <template #icon>
            <CircleCheck :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.offlineNodes')"
          :value="stats.offline"
          accent="red"
          accent-side="left"
          :pulse="stats.offline > 0"
        >
          <template #icon>
            <CircleX :size="16" />
          </template>
        </OpsStatCard>
        <OpsStatCard
          :label="t('platformOps.monitoring.outdatedAgents')"
          :value="stats.outdated"
          :sub="t('platformOps.monitoring.latestAgent', { version: stats.latest_version || '—' })"
          accent="orange"
          accent-side="left"
        >
          <template #icon>
            <ShieldAlert :size="16" />
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
              :placeholder="t('platformOps.monitoring.searchNodes')"
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
                value="online"
                label="Online"
              /><el-option
                value="offline"
                label="Offline"
              />
            </el-select>
            <el-select
              v-model="filters.role"
              clearable
              class="platform-monitoring-page__filter"
              :aria-label="t('platformOps.monitoring.filterRole')"
              :placeholder="t('platformOps.monitoring.filterRole')"
            >
              <el-option
                value="agent"
                label="Agent"
              /><el-option
                value="proxy"
                label="Proxy"
              /><el-option
                value="gateway"
                label="Gateway"
              />
            </el-select>
            <el-input
              v-model="filters.org"
              clearable
              class="platform-monitoring-page__filter"
              :placeholder="t('platformOps.monitoring.filterAccount')"
            />
            <el-button
              v-if="filters.search || filters.status || filters.role || filters.org"
              text
              @click="resetFilters"
            >
              {{ t('platformOps.monitoring.resetFilters') }}
            </el-button>
          </div>
        </template>
        <template #toolbar-utility>
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
              :label="t('platformOps.monitoring.node')"
              min-width="240"
            >
              <template #default="{ row }">
                <button
                  type="button"
                  class="platform-monitoring-page__title-button"
                  @click="openDrawer(row)"
                >
                  {{ row.hostname }}
                </button><span class="platform-monitoring-page__cell-meta">{{ row.os_name || '—' }}{{ row.ip_address ? ` · ${row.ip_address}` : '' }}</span>
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
              prop="role"
              :label="t('platformOps.monitoring.colRole')"
              width="110"
            />
            <el-table-column
              :label="t('platformOps.monitoring.colAgentVersion')"
              width="150"
            >
              <template #default="{ row }">
                <span>{{ row.agent_version || '—' }}</span><span
                  v-if="isOutdated(row)"
                  class="platform-monitoring-page__cell-meta"
                >{{ t('platformOps.monitoring.outdated') }}</span>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('platformOps.monitoring.lastSeen')"
              width="170"
            >
              <template #default="{ row }">
                {{ displayTime(row.last_seen_at || row.updated_at) }}
              </template>
            </el-table-column>
            <template #empty>
              <el-empty
                :description="t('platformOps.monitoring.emptyNodes')"
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
          <h2>{{ selected?.hostname }}</h2><p>{{ selected?.status }} · {{ selected?.role }}</p>
        </div>
      </template>
      <template v-if="selected">
        <section class="platform-monitoring-drawer__section">
          <h3>{{ t('platformOps.monitoring.connectionDetails') }}</h3><div class="platform-monitoring-drawer__grid">
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.account') }}</span><strong>{{ selected.organization_key }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.lastSeen') }}</span><strong>{{ displayTime(selected.last_seen_at) }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.ipAddress') }}</span><strong>{{ selected.ip_address || '—' }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.platform') }}</span><strong>{{ selected.os_name || '—' }}</strong>
            </div>
          </div>
        </section>
        <section class="platform-monitoring-drawer__section">
          <h3>{{ t('platformOps.monitoring.agentDetails') }}</h3><div class="platform-monitoring-drawer__grid">
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.currentVersion') }}</span><strong>{{ selected.agent_version || '—' }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>{{ t('platformOps.monitoring.latestVersion') }}</span><strong>{{ stats.latest_version || '—' }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>Architecture</span><strong>{{ metadataValue('arch') }}</strong>
            </div>
            <div class="platform-monitoring-drawer__field">
              <span>Environment</span><strong>{{ metadataValue('environment') }}</strong>
            </div>
          </div>
        </section>
        <div class="platform-monitoring-drawer__actions">
          <RouterLink
            class="overview-text-link"
            to="/platform-ops/platform/agent-releases"
          >
            {{ t('platformOps.monitoring.viewAgentReleases') }}
          </RouterLink>
        </div>
      </template>
    </el-drawer>
  </ModulePage>
</template>
