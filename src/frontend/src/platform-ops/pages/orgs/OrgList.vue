<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import {
  Building2,
  CircleAlert,
  CircleCheckBig,
  MoreHorizontal,
  RefreshCw,
  Search,
  Server,
} from 'lucide-vue-next'
import HflPagination from '../../../components/HflPagination.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import DangerConfirmDialog from '../../../components/DangerConfirmDialog.vue'
import ModulePage from '../../../components/ModulePage.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import { useDebouncedAction } from '../../../composables/useDebouncedAction'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsActiveTag from '../../components/PlatformOpsActiveTag.vue'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import PlatformOpsUserLink from '../../components/PlatformOpsUserLink.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { updatePlatformOrg } from '../../lib/platformOpsApi'
import {
  listPlatformOpsOrganizations,
  type PlatformOpsOrganization,
  type PlatformOpsOrganizationStats,
} from '../../lib/platformOpsUserApi'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()

const rows = ref<PlatformOpsOrganization[]>([])
const stats = ref<PlatformOpsOrganizationStats>({ total: 0, active: 0, inactive: 0, with_incidents: 0 })
const busy = ref(false)
const rowActionId = ref<number | null>(null)
const deactivateTarget = ref<PlatformOpsOrganization | null>(null)
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({
  search: String(route.query.search || ''),
  status: String(route.query.status || ''),
  health: String(route.query.health || ''),
})
const { schedule: scheduleSearch, runNow: runFiltersNow } = useDebouncedAction(applyFilters)

async function syncQuery() {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries(filters)) {
    if (value.trim()) query[key] = value.trim()
  }
  await router.replace({ query })
}

async function load() {
  busy.value = true
  try {
    const data = await listPlatformOpsOrganizations({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters,
    })
    rows.value = data.results
    stats.value = data.stats || stats.value
    pagination.count = data.count
  } catch (error) {
    rows.value = []
    pagination.count = 0
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.orgs.loadFailed')), grouping: true })
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
  filters.search = ''
  filters.status = ''
  filters.health = ''
  runFiltersNow()
}

async function toggleOrganization(row: PlatformOpsOrganization) {
  if (rowActionId.value) return
  if (row.is_active) {
    deactivateTarget.value = row
    return
  }

  await updateActiveState(row)
}

async function updateActiveState(row: PlatformOpsOrganization) {
  rowActionId.value = row.id
  try {
    await updatePlatformOrg(row.id, { is_active: !row.is_active })
    ElMessage.success({ message: t('platformOps.orgs.saveSuccess'), grouping: true })
    await load()
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.orgs.saveFailed')), grouping: true })
  } finally {
    rowActionId.value = null
  }
}

async function confirmDeactivate() {
  const target = deactivateTarget.value
  if (!target) return
  await updateActiveState(target)
  deactivateTarget.value = null
}

function handleRowAction(command: string, row: PlatformOpsOrganization) {
  if (command === 'view') void router.push(`/platform-ops/orgs/${row.id}`)
  if (command === 'user' && row.owner_user_id) void router.push(`/platform-ops/users/${row.owner_user_id}`)
  if (command === 'monitoring') {
    void router.push(`/platform-ops/alert-center/incidents?org=${encodeURIComponent(row.key)}`)
  }
  if (command === 'toggle') void toggleOrganization(row)
}

function attentionCount(row: PlatformOpsOrganization) {
  return (row.failed_task_count || 0) + (row.incident_count || 0)
}

onMounted(load)
watch(() => filters.search, scheduleSearch)
watch(() => [filters.status, filters.health], runFiltersNow)
watch(() => [pagination.page, pagination.pageSize], load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="platform-account-page">
      <div class="platform-account-page__lead">
        <p>{{ t('platformOps.orgs.subtitle') }}</p>
        <el-button type="primary" @click="router.push('/platform-ops/users?create=1')">
          {{ t('platformOps.users.create') }}
        </el-button>
      </div>

      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard :label="t('platformOps.orgs.statTotal')" :value="stats.total" accent="indigo" accent-side="left">
          <template #icon><Building2 :size="16" /></template>
        </OpsStatCard>
        <OpsStatCard :label="t('platformOps.orgs.statActive')" :value="stats.active" accent="green" accent-side="left">
          <template #icon><CircleCheckBig :size="16" /></template>
        </OpsStatCard>
        <OpsStatCard :label="t('platformOps.orgs.statInactive')" :value="stats.inactive" accent="orange" accent-side="left">
          <template #icon><Server :size="16" /></template>
        </OpsStatCard>
        <OpsStatCard :label="t('platformOps.orgs.statWithIncidents')" :value="stats.with_incidents" accent="red" accent-side="left" :pulse="stats.with_incidents > 0">
          <template #icon><CircleAlert :size="16" /></template>
        </OpsStatCard>
      </div>

      <HflTablePanel fill>
        <template #toolbar>
          <div class="platform-account-page__filters">
            <el-input
              v-model="filters.search"
              clearable
              class="platform-account-page__search"
              :placeholder="t('platformOps.orgs.searchPlaceholder')"
              :aria-label="t('platformOps.orgs.searchPlaceholder')"
            >
              <template #prefix><Search :size="15" /></template>
            </el-input>
            <el-select
              v-model="filters.status"
              clearable
              class="platform-account-page__filter"
              :placeholder="t('platformOps.account.filterStatus')"
              :aria-label="t('platformOps.account.filterStatus')"
            >
              <el-option value="active" :label="t('platformOps.users.active')" />
              <el-option value="inactive" :label="t('platformOps.users.inactive')" />
            </el-select>
            <el-select
              v-model="filters.health"
              clearable
              class="platform-account-page__filter"
              :placeholder="t('platformOps.orgs.filterHealth')"
              :aria-label="t('platformOps.orgs.filterHealth')"
            >
              <el-option value="healthy" :label="t('platformOps.orgs.healthHealthy')" />
              <el-option value="attention" :label="t('platformOps.orgs.healthAttention')" />
            </el-select>
            <el-button v-if="filters.search || filters.status || filters.health" text @click="resetFilters">
              {{ t('platformOps.account.resetFilters') }}
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
            <RefreshCw :size="16" :class="{ 'is-spinning': busy }" />
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
            <el-table-column :label="t('platformOps.orgs.organization')" min-width="220">
              <template #default="{ row }">
                <PlatformOpsOrgLink :org-id="row.id" :org-key="row.key" :label="row.name" />
                <span class="platform-account-page__cell-meta platform-account-page__cell-meta--mono">{{ row.key }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.orgs.colOwner')" min-width="210">
              <template #default="{ row }">
                <PlatformOpsUserLink
                  v-if="row.owner_user_id"
                  :user-id="row.owner_user_id"
                  :display-name="row.owner_display_name || row.owner_email || '—'"
                />
                <span v-else>{{ row.owner_email || '—' }}</span>
                <span v-if="row.owner_email && row.owner_display_name !== row.owner_email" class="platform-account-page__cell-meta">
                  {{ row.owner_email }}
                </span>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.orgs.colActive')" width="110">
              <template #default="{ row }"><PlatformOpsActiveTag :active="row.is_active" /></template>
            </el-table-column>
            <el-table-column :label="t('platformOps.orgs.colNodes')" width="92" align="center">
              <template #default="{ row }">{{ row.node_count || 0 }}</template>
            </el-table-column>
            <el-table-column :label="t('platformOps.orgs.colFailedTasks')" width="118" align="center">
              <template #default="{ row }">
                <span :class="{ 'platform-account-page__attention': (row.failed_task_count || 0) > 0 }">
                  {{ row.failed_task_count || 0 }}
                </span>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.orgs.colIncidents')" width="110" align="center">
              <template #default="{ row }">
                <span :class="{ 'platform-account-page__attention': (row.incident_count || 0) > 0 }">
                  {{ row.incident_count || 0 }}
                  <span class="sr-only">{{ attentionCount(row) > 0 ? t('platformOps.orgs.healthAttention') : '' }}</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.orgs.colCreated')" width="176">
              <template #default="{ row }">{{ formatLocalDateTime(row.created_at, '—') }}</template>
            </el-table-column>
            <el-table-column width="64" fixed="right" align="center">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="handleRowAction($event, row)">
                  <el-button
                    text
                    class="platform-account-page__row-menu"
                    :loading="rowActionId === row.id"
                    :aria-label="t('platformOps.account.rowActions', { name: row.name })"
                  >
                    <MoreHorizontal :size="18" />
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="view">{{ t('platformOps.account.viewDetails') }}</el-dropdown-item>
                      <el-dropdown-item command="user" :disabled="!row.owner_user_id">{{ t('platformOps.orgs.viewUser') }}</el-dropdown-item>
                      <el-dropdown-item command="monitoring">{{ t('platformOps.orgs.viewMonitoring') }}</el-dropdown-item>
                      <el-dropdown-item command="toggle">
                        {{ row.is_active ? t('platformOps.orgs.deactivate') : t('platformOps.orgs.activate') }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty :description="t('platformOps.orgs.empty')" :image-size="72" />
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

    <DangerConfirmDialog
      v-if="deactivateTarget"
      :model-value="true"
      :title="t('platformOps.orgs.deactivateConfirmTitle')"
      :message="t('platformOps.orgs.deactivateConfirmMessage', { name: deactivateTarget.name })"
      :warning="t('platformOps.orgs.deactivateConfirmWarning')"
      :cancel-text="t('common.cancel')"
      :confirm-text="t('platformOps.orgs.deactivateConfirmAction')"
      :loading="rowActionId === deactivateTarget.id"
      @update:model-value="deactivateTarget = null"
      @confirm="confirmDeactivate"
      @cancel="deactivateTarget = null"
    />
  </ModulePage>
</template>
