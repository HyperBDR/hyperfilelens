<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { RefreshCw } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import PlatformOpsListToolbarActions from '../../components/PlatformOpsListToolbarActions.vue'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import HflPagination from '../../../components/HflPagination.vue'
import { usePlatformOpsListSelection } from '../../composables/usePlatformOpsListSelection'
import { usePlatformOpsReadonlyListActions } from '../../composables/usePlatformOpsReadonlyListActions'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { fetchMonitoringTasks } from '../../lib/platformOpsApi'
import { apiErrorMessage } from '../../../lib/api'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import PlatformOpsTimeCell from '../../components/PlatformOpsTimeCell.vue'
import TaskTypeLabel from '../../../components/TaskTypeLabel.vue'
import { PLATFORM_OPS_LIST_TABLE_MAX_HEIGHT, PLATFORM_OPS_TABLE_HEADER_STYLE } from '../../lib/tableUi'

const { t } = useI18n()
const route = useRoute()
const sideNav = usePlatformOpsSideNav()

type TaskRow = Record<string, unknown> & { id: number; organization_id?: number }

const { selected, onSelectionChange, clearSelection } = usePlatformOpsListSelection<TaskRow>()
const { editDisabled, deleteDisabled, onAdd, onEdit, onDelete } = usePlatformOpsReadonlyListActions(selected)

const rows = ref<TaskRow[]>([])
const busy = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

async function load() {
  busy.value = true
  try {
    const data = await fetchMonitoringTasks({
      page: currentPage.value,
      page_size: pageSize.value,
      org: route.query.org as string | undefined,
      status: route.query.status as string | undefined,
    })
    rows.value = data.results as TaskRow[]
    totalCount.value = data.count
    clearSelection()
  } catch (err) {
    rows.value = []
    totalCount.value = 0
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.monitoring.loadFailed')), grouping: true })
  } finally {
    busy.value = false
  }
}

onMounted(load)
watch([currentPage, pageSize], load)
watch(() => route.query, () => {
  currentPage.value = 1
  void load()
})
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="hfl-list-shell hfl-list-shell--fill">
      <div class="hfl-list-panel hfl-list-panel--fill">
        <div class="hfl-list-toolbar">
          <PlatformOpsListToolbarActions
            add-disabled
            :edit-disabled="editDisabled"
            :delete-disabled="deleteDisabled"
            @add="onAdd"
            @edit="onEdit"
            @delete="onDelete"
          />
          <div class="hfl-list-toolbar__right">
            <el-button
              class="hfl-refresh-button"
              :title="t('common.refresh')"
              :aria-label="t('common.refresh')"
              :disabled="busy"
              @click="load"
            >
              <RefreshCw :size="16" :class="{ 'is-spinning': busy }" />
            </el-button>
          </div>
        </div>

        <el-table
          v-table-column-resize="'platformOps.monitoring.tasks'"
          :data="rows"
          stripe
          row-key="id"
          class="hfl-list-table"
          :loading="busy"
          :max-height="PLATFORM_OPS_LIST_TABLE_MAX_HEIGHT"
          :header-cell-style="PLATFORM_OPS_TABLE_HEADER_STYLE"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" min-width="35" />
          <el-table-column :label="t('platformOps.orgs.colKey')" min-width="120">
            <template #default="{ row }">
              <PlatformOpsOrgLink :org-id="row.organization_id as number" :org-key="row.organization_key as string" />
            </template>
          </el-table-column>
          <el-table-column prop="display_name" :label="t('platformOps.monitoring.colTask')" min-width="160" />
          <el-table-column :label="t('platformOps.monitoring.colTaskType')" min-width="150">
            <template #default="{ row }">
              <TaskTypeLabel :type="String(row.task_type || '')" />
            </template>
          </el-table-column>
          <el-table-column :label="t('platformOps.monitoring.colStatus')" min-width="120">
            <template #default="{ row }">
              <PlatformOpsStatusPill :status="row.status as string" />
            </template>
          </el-table-column>
          <el-table-column prop="error_message" :label="t('platformOps.monitoring.colError')" min-width="180" />
          <el-table-column :label="t('platformOps.monitoring.colFinished')" min-width="170">
            <template #default="{ row }">
              <PlatformOpsTimeCell :value="row.finished_at as string" />
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="t('platformOps.monitoring.emptyTasks')" :image-size="80" />
          </template>
        </el-table>

        <div class="hfl-list-footer">
          <HflPagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            class="hfl-list-footer__pagination"
            :total="totalCount"
          />
        </div>
      </div>
    </div>
  </ModulePage>
</template>
