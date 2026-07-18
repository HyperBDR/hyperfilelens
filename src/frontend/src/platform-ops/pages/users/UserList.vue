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
import PlatformOpsTimeCell from '../../components/PlatformOpsTimeCell.vue'
import PlatformOpsUserLink from '../../components/PlatformOpsUserLink.vue'
import HflTypeLabel from '../../../components/HflTypeLabel.vue'
import DangerConfirmDialog, { type DangerConfirmItem } from '../../../components/DangerConfirmDialog.vue'
import { usePlatformOpsListSelection } from '../../composables/usePlatformOpsListSelection'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import {
  createPlatformOpsUser,
  deletePlatformOpsUsers,
  listPlatformOpsUsers,
  type PlatformOpsUser,
} from '../../lib/platformOpsUserApi'
import { apiErrorMessage } from '../../../lib/api'
import { PLATFORM_OPS_LIST_TABLE_MAX_HEIGHT, PLATFORM_OPS_TABLE_HEADER_STYLE } from '../../lib/tableUi'
import { useListSearch } from '../../../composables/useListSearch'

const { t } = useI18n()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()
const { selected, editDisabled, deleteDisabled, onSelectionChange, clearSelection } =
  usePlatformOpsListSelection<PlatformOpsUser>()

const rows = ref<PlatformOpsUser[]>([])
const busy = ref(false)
const search = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)
const deleteOpen = ref(false)
const pendingDelete = ref<PlatformOpsUser[]>([])
const deleteItems = computed<DangerConfirmItem[]>(() => pendingDelete.value.map((row) => ({
  key: row.id,
  name: row.display_name || row.email,
  description: row.email,
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
const createForm = ref({
  email: '',
  password: '',
  is_active: true,
  is_staff: false,
})

async function load() {
  busy.value = true
  try {
    const data = await listPlatformOpsUsers({
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
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.users.loadFailed')), grouping: true })
  } finally {
    busy.value = false
  }
}

function openCreate() {
  createForm.value = { email: '', password: '', is_active: true, is_staff: false }
  createOpen.value = true
}

async function submitCreate() {
  createBusy.value = true
  try {
    const user = await createPlatformOpsUser(createForm.value)
    createOpen.value = false
    ElMessage.success({ message: t('platformOps.users.createSuccess'), grouping: true })
    await load()
    router.push(`/platform-ops/users/${user.id}`)
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.users.createFailed')), grouping: true })
  } finally {
    createBusy.value = false
  }
}

function goDetail(row: PlatformOpsUser) {
  router.push(`/platform-ops/users/${row.id}`)
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
    await deletePlatformOpsUsers(targets.map((row) => row.id))
    ElMessage.success({ message: t('platformOps.list.deleteUsersSuccess'), grouping: true })
    await load()
    deleteOpen.value = false
    pendingDelete.value = []
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.list.deleteUsersFailed')), grouping: true })
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
              :placeholder="t('platformOps.users.searchPlaceholder')"
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
          v-table-column-resize="'platformOps.users.list'"
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
          <el-table-column :label="t('platformOps.users.colName')" min-width="140">
            <template #default="{ row }">
              <PlatformOpsUserLink :user-id="row.id" :display-name="row.display_name" />
            </template>
          </el-table-column>
          <el-table-column prop="email" :label="t('platformOps.users.colEmail')" min-width="200" />
          <el-table-column :label="t('platformOps.users.colStaff')" min-width="150" align="center">
            <template #default="{ row }">
              <HflTypeLabel :label="row.is_staff ? t('common.yes') : t('common.no')" />
            </template>
          </el-table-column>
          <el-table-column :label="t('platformOps.users.colActive')" min-width="100" align="center">
            <template #default="{ row }">
              <PlatformOpsActiveTag :active="row.is_active" />
            </template>
          </el-table-column>
          <el-table-column :label="t('platformOps.users.colOrgs')" min-width="90" align="center">
            <template #default="{ row }">{{ row.membership_count ?? 0 }}</template>
          </el-table-column>
          <el-table-column :label="t('platformOps.users.colJoined')" min-width="170">
            <template #default="{ row }">
              <PlatformOpsTimeCell :value="row.date_joined" />
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="t('platformOps.users.empty')" :image-size="80" />
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

    <el-dialog v-model="createOpen" :title="t('platformOps.users.createTitle')" width="480px">
      <el-form label-width="120px" @submit.prevent="submitCreate">
        <el-form-item :label="t('platformOps.users.fieldEmail')" required>
          <el-input v-model="createForm.email" type="email" autocomplete="off" />
        </el-form-item>
        <el-form-item :label="t('platformOps.users.fieldPassword')" required>
          <el-input v-model="createForm.password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item :label="t('platformOps.users.fieldActive')">
          <el-switch v-model="createForm.is_active" />
        </el-form-item>
        <el-form-item :label="t('platformOps.users.fieldStaff')">
          <el-switch v-model="createForm.is_staff" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="createBusy" @click="submitCreate">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
    <DangerConfirmDialog
      v-model="deleteOpen"
      :title="t('platformOps.list.deleteUsersTitle')"
      :message="t('platformOps.list.deleteUsersConfirm', { n: pendingDelete.length })"
      :items="deleteItems"
      :items-heading="t('platformOps.list.deleteUsersTitle')"
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
