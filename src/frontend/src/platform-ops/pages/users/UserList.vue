<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
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
import { apiErrorMessage, type ApiError } from '../../../lib/api'
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
const createFormRef = ref<FormInstance | null>(null)
const createForm = ref({
  email: '',
  password: '',
  confirm_password: '',
  is_active: true,
})
const createFieldErrors = ref({
  email: '',
  password: '',
})
const supportedPasswordPattern = /^[A-Za-z\d.!"@#$%&'*():;\\+/=?^_`{|}~><-]+$/
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const createRules = computed<FormRules>(() => ({
  email: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        const email = String(value || '').trim()
        if (!email) {
          callback(new Error(t('platformOps.users.validateEmailRequired')))
          return
        }
        if (!emailPattern.test(email)) {
          callback(new Error(t('platformOps.users.validateEmailInvalid')))
          return
        }
        callback()
      },
      trigger: ['blur', 'change'],
    },
  ],
  password: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        const password = String(value || '')
        if (!password) {
          callback(new Error(t('platformOps.users.validatePasswordRequired')))
          return
        }
        const valid = password.length >= 8
          && password.length <= 20
          && supportedPasswordPattern.test(password)
          && /[a-z]/.test(password)
          && /[A-Z]/.test(password)
          && /\d/.test(password)
        callback(valid ? undefined : new Error(t('platformOps.users.validatePasswordFormat')))
      },
      trigger: ['blur', 'change'],
    },
  ],
  confirm_password: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (!value) {
          callback(new Error(t('platformOps.users.validateConfirmPasswordRequired')))
          return
        }
        callback(value === createForm.value.password
          ? undefined
          : new Error(t('platformOps.users.validateConfirmPasswordMismatch')))
      },
      trigger: ['blur', 'change'],
    },
  ],
}))

function clearCreateFieldError(field: 'email' | 'password') {
  createFieldErrors.value[field] = ''
}

function applyCreateFieldErrors(error: unknown) {
  const fields = (error as Partial<ApiError> | null)?.fields
  if (!fields) return false

  let applied = false
  for (const field of ['email', 'password'] as const) {
    const message = fields[field]?.[0]
    if (message) {
      createFieldErrors.value[field] = message
      applied = true
    }
  }
  return applied
}

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

async function openCreate() {
  createForm.value = { email: '', password: '', confirm_password: '', is_active: true }
  createFieldErrors.value = { email: '', password: '' }
  createOpen.value = true
  await nextTick()
  createFormRef.value?.clearValidate()
}

async function submitCreate() {
  if (createBusy.value) return
  createFieldErrors.value = { email: '', password: '' }
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  createBusy.value = true
  try {
    const user = await createPlatformOpsUser({
      email: createForm.value.email.trim(),
      password: createForm.value.password,
      is_active: createForm.value.is_active,
    })
    createOpen.value = false
    ElMessage.success({ message: t('platformOps.users.createSuccess'), grouping: true })
    await load()
    router.push(`/platform-ops/users/${user.id}`)
  } catch (err) {
    if (!applyCreateFieldErrors(err)) {
      ElMessage.error({ message: apiErrorMessage(err, t('platformOps.users.createFailed')), grouping: true })
    }
  } finally {
    createBusy.value = false
  }
}

function closeCreate(done?: () => void) {
  if (createBusy.value) return
  if (done) {
    done()
    return
  }
  createOpen.value = false
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

    <el-dialog
      v-model="createOpen"
      :title="t('platformOps.users.createTitle')"
      width="480px"
      :before-close="closeCreate"
      :close-on-click-modal="!createBusy"
      :close-on-press-escape="!createBusy"
      :show-close="!createBusy"
    >
      <el-alert
        class="create-user-hint"
        type="info"
        :title="t('platformOps.users.createTenantHint')"
        :closable="false"
        show-icon
      />
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-position="top"
        @submit.prevent="submitCreate"
      >
        <el-form-item
          prop="email"
          :label="t('platformOps.users.fieldEmail')"
          :error="createFieldErrors.email"
        >
          <el-input
            v-model="createForm.email"
            type="email"
            autocomplete="off"
            :disabled="createBusy"
            @input="clearCreateFieldError('email')"
          />
        </el-form-item>
        <el-form-item
          prop="password"
          :label="t('platformOps.users.fieldInitialPassword')"
          :error="createFieldErrors.password"
        >
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            autocomplete="new-password"
            :disabled="createBusy"
            @input="clearCreateFieldError('password')"
          />
          <div class="create-user-password-hint">
            {{ t('platformOps.users.passwordRequirements') }}
          </div>
        </el-form-item>
        <el-form-item
          prop="confirm_password"
          :label="t('platformOps.users.fieldConfirmPassword')"
        >
          <el-input
            v-model="createForm.confirm_password"
            type="password"
            show-password
            autocomplete="new-password"
            :disabled="createBusy"
          />
        </el-form-item>
        <el-form-item :label="t('platformOps.users.fieldActive')">
          <el-switch
            v-model="createForm.is_active"
            :disabled="createBusy"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button
          :disabled="createBusy"
          @click="closeCreate()"
        >
          {{ t('common.cancel') }}
        </el-button>
        <el-button
          type="primary"
          :loading="createBusy"
          @click="submitCreate"
        >
          {{ t('common.confirm') }}
        </el-button>
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

<style scoped>
.create-user-hint {
  margin-bottom: 20px;
}

.create-user-password-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
  margin-top: 6px;
}
</style>
