<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { RefreshCw, Search } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import HflPagination from '../../../components/HflPagination.vue'
import PlatformOpsActiveTag from '../../components/PlatformOpsActiveTag.vue'
import PlatformOpsListToolbarActions from '../../components/PlatformOpsListToolbarActions.vue'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import PlatformOpsTimeCell from '../../components/PlatformOpsTimeCell.vue'
import DangerConfirmDialog, { type DangerConfirmItem } from '../../../components/DangerConfirmDialog.vue'
import { usePlatformOpsListSelection } from '../../composables/usePlatformOpsListSelection'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { createPlatformOrg, deletePlatformOrgs } from '../../lib/platformOpsApi'
import {
  listPlatformOpsOrganizations,
  listPlatformOpsUsers,
  type PlatformOpsOrganization,
  type PlatformOpsUser,
} from '../../lib/platformOpsUserApi'
import { apiErrorMessage } from '../../../lib/api'
import { PLATFORM_OPS_LIST_TABLE_MAX_HEIGHT, PLATFORM_OPS_TABLE_HEADER_STYLE } from '../../lib/tableUi'
import { useListSearch } from '../../../composables/useListSearch'

const { t } = useI18n()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()
const { selected, editDisabled, deleteDisabled, onSelectionChange, clearSelection } =
  usePlatformOpsListSelection<PlatformOpsOrganization>()

const rows = ref<PlatformOpsOrganization[]>([])
const busy = ref(false)
const search = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)
const deleteOpen = ref(false)
const pendingDelete = ref<PlatformOpsOrganization[]>([])
const deleteItems = computed<DangerConfirmItem[]>(() => pendingDelete.value.map((row) => ({
  key: row.id,
  name: row.name,
  description: row.key,
  hint: row.owner_email || undefined,
})))
const { appliedSearch, clearSearch } = useListSearch(search, () => {
  if (currentPage.value !== 1) {
    currentPage.value = 1
    return
  }
  void load()
})

const createOpen = ref(false)
const createBusy = ref(false)
const ownerOptions = ref<PlatformOpsUser[]>([])
const ownerSearchBusy = ref(false)
const createForm = ref({
  key: '',
  name: '',
  owner_user_id: null as number | null,
  is_active: true,
})

async function load() {
  busy.value = true
  try {
    const data = await listPlatformOpsOrganizations({
      page: currentPage.value,
      page_size: pageSize.value,
      search: appliedSearch.value,
    })
    rows.value = data.results
    totalCount.value = data.count
    clearSelection()
  } catch (err) {
    rows.value = []
    totalCount.value = 0
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.orgs.loadFailed')), grouping: true })
  } finally {
    busy.value = false
  }
}

async function searchOwners(query: string) {
  ownerSearchBusy.value = true
  try {
    const data = await listPlatformOpsUsers({ search: query, page_size: 20 })
    ownerOptions.value = data.results
  } catch {
    ownerOptions.value = []
  } finally {
    ownerSearchBusy.value = false
  }
}

function openCreate() {
  createForm.value = { key: '', name: '', owner_user_id: null, is_active: true }
  createOpen.value = true
  void searchOwners('')
}

async function submitCreate() {
  if (!createForm.value.owner_user_id) {
    ElMessage.warning({ message: t('platformOps.list.fieldOwnerUserPh'), grouping: true })
    return
  }
  createBusy.value = true
  try {
    const org = await createPlatformOrg({
      key: createForm.value.key.trim(),
      name: createForm.value.name.trim(),
      owner_user_id: createForm.value.owner_user_id,
      is_active: createForm.value.is_active,
    }) as PlatformOpsOrganization
    createOpen.value = false
    ElMessage.success({ message: t('platformOps.list.createOrgSuccess'), grouping: true })
    await load()
    router.push(`/platform-ops/orgs/${org.id}`)
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.list.createOrgFailed')), grouping: true })
  } finally {
    createBusy.value = false
  }
}

function goDetail(row: PlatformOpsOrganization) {
  router.push(`/platform-ops/orgs/${row.id}`)
}

function editSelected() {
  if (editDisabled.value) {
    ElMessage.warning({ message: t('platformOps.list.msgSelectOne'), grouping: true })
    return
  }
  goDetail(selected.value[0])
}

function deleteSelected() {
  if (deleteDisabled.value) {
    ElMessage.warning({ message: t('platformOps.list.msgSelectRow'), grouping: true })
    return
  }
  pendingDelete.value = [...selected.value]
  deleteOpen.value = true
}

async function confirmDelete() {
  const targets = [...pendingDelete.value]
  if (!targets.length) return
  busy.value = true
  try {
    await deletePlatformOrgs(targets.map((row) => row.id))
    ElMessage.success({ message: t('platformOps.list.deleteOrgsSuccess'), grouping: true })
    await load()
    deleteOpen.value = false
    pendingDelete.value = []
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.list.deleteOrgsFailed')), grouping: true })
  } finally {
    busy.value = false
  }
}

onMounted(load)
watch([currentPage, pageSize], load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="hfl-list-shell hfl-list-shell--fill">
      <div class="hfl-list-panel hfl-list-panel--fill">
        <div class="hfl-list-toolbar">
          <PlatformOpsListToolbarActions
            :edit-disabled="editDisabled"
            :delete-disabled="deleteDisabled"
            @add="openCreate"
            @edit="editSelected"
            @delete="deleteSelected"
          />
          <div class="hfl-list-toolbar__right">
            <el-input
              v-model="search"
              clearable
              size="small"
              :placeholder="t('platformOps.orgs.searchPlaceholder')"
              class="hfl-list-search"
              @clear="clearSearch"
            >
              <template #prefix>
                <Search :size="16" class="hfl-list-search__icon" />
              </template>
            </el-input>
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
          v-table-column-resize="'platformOps.orgs.list'"
          v-loading="busy"
          :data="rows"
          stripe
          row-key="id"
          class="hfl-list-table"
          :max-height="PLATFORM_OPS_LIST_TABLE_MAX_HEIGHT"
          :header-cell-style="PLATFORM_OPS_TABLE_HEADER_STYLE"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" min-width="35" />
          <el-table-column :label="t('platformOps.orgs.colName')" min-width="160">
            <template #default="{ row }">
              <PlatformOpsOrgLink :org-id="row.id" :org-key="row.key" :label="row.name" />
            </template>
          </el-table-column>
          <el-table-column prop="key" :label="t('platformOps.orgs.colKey')" min-width="140" />
          <el-table-column :label="t('platformOps.orgs.colOwner')" min-width="180">
            <template #default="{ row }">{{ row.owner_email || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('platformOps.orgs.colMembers')" min-width="90" align="center">
            <template #default="{ row }">{{ row.member_count ?? 0 }}</template>
          </el-table-column>
          <el-table-column :label="t('platformOps.orgs.colActive')" min-width="100" align="center">
            <template #default="{ row }">
              <PlatformOpsActiveTag :active="row.is_active" />
            </template>
          </el-table-column>
          <el-table-column :label="t('platformOps.orgs.colCreated')" min-width="170">
            <template #default="{ row }">
              <PlatformOpsTimeCell :value="row.created_at" />
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="t('platformOps.orgs.empty')" :image-size="80" />
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

    <el-dialog v-model="createOpen" :title="t('platformOps.list.createOrgTitle')" width="520px">
      <el-form label-width="140px" @submit.prevent="submitCreate">
        <el-form-item :label="t('platformOps.list.fieldOrgKey')" required>
          <el-input v-model="createForm.key" autocomplete="off" />
        </el-form-item>
        <el-form-item :label="t('platformOps.list.fieldOrgName')" required>
          <el-input v-model="createForm.name" autocomplete="off" />
        </el-form-item>
        <el-form-item :label="t('platformOps.list.fieldOwnerUser')" required>
          <el-select
            v-model="createForm.owner_user_id"
            filterable
            remote
            reserve-keyword
            :remote-method="searchOwners"
            :loading="ownerSearchBusy"
            :placeholder="t('platformOps.list.fieldOwnerUserPh')"
            class="w-full"
          >
            <el-option
              v-for="user in ownerOptions"
              :key="user.id"
              :label="user.email"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('platformOps.orgs.colActive')">
          <el-switch v-model="createForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="createBusy" @click="submitCreate">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
    <DangerConfirmDialog
      v-model="deleteOpen"
      :title="t('platformOps.list.deleteOrgsTitle')"
      :message="t('platformOps.list.deleteOrgsConfirm', { n: pendingDelete.length })"
      :items="deleteItems"
      :items-heading="t('platformOps.list.deleteOrgsTitle')"
      confirm-mode="keyword"
      :confirm-keyword="t('common.deleteKeyword')"
      :cancel-text="t('common.cancel')"
      :confirm-text="t('common.delete')"
      :loading="busy"
      @confirm="confirmDelete"
      @cancel="pendingDelete = []"
    />
  </ModulePage>
</template>

<style scoped>
.w-full {
  width: 100%;
}
</style>
