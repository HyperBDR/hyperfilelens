<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  Clock3,
  MoreHorizontal,
  RefreshCw,
  Search,
  UserCheck,
  UserRoundCog,
  UserX,
  Users,
} from 'lucide-vue-next'
import HflPagination from '../../../components/HflPagination.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import HflTypeLabel from '../../../components/HflTypeLabel.vue'
import DangerConfirmDialog from '../../../components/DangerConfirmDialog.vue'
import ModulePage from '../../../components/ModulePage.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import { useDebouncedAction } from '../../../composables/useDebouncedAction'
import { useResponsiveDrawerWidth } from '../../../composables/useResponsiveDrawerWidth'
import { apiErrorMessage, type ApiError } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsActiveTag from '../../components/PlatformOpsActiveTag.vue'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import PlatformOpsUserLink from '../../components/PlatformOpsUserLink.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import {
  createPlatformOpsUser,
  listPlatformOpsUsers,
  updatePlatformOpsUser,
  type PlatformOpsUser,
  type PlatformOpsUserStats,
} from '../../lib/platformOpsUserApi'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()
const { drawerSize } = useResponsiveDrawerWidth(3)

const rows = ref<PlatformOpsUser[]>([])
const stats = ref<PlatformOpsUserStats>({ total: 0, active: 0, inactive: 0, never_signed_in: 0 })
const busy = ref(false)
const rowActionId = ref<number | null>(null)
const deactivateTarget = ref<PlatformOpsUser | null>(null)
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({
  search: String(route.query.search || ''),
  status: String(route.query.status || ''),
  account_type: String(route.query.account_type || ''),
})
const { schedule: scheduleSearch, runNow: runFiltersNow } = useDebouncedAction(applyFilters)

const createOpen = ref(false)
const createBusy = ref(false)
const createFormRef = ref<FormInstance | null>(null)
const createForm = reactive({
  email: '',
  first_name: '',
  last_name: '',
  account_type: 'customer' as 'customer' | 'administrator',
  organization_name: '',
  password: '',
  confirm_password: '',
  is_active: true,
})
const createFieldErrors = reactive({ email: '', password: '' })
const supportedPasswordPattern = /^[A-Za-z\d.!"@#$%&'*():;\\+/=?^_`{|}~><-]+$/
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const createRules = computed<FormRules>(() => ({
  email: [{
    validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
      const email = String(value || '').trim()
      if (!email) return callback(new Error(t('platformOps.users.validateEmailRequired')))
      if (!emailPattern.test(email)) return callback(new Error(t('platformOps.users.validateEmailInvalid')))
      callback()
    },
    trigger: ['blur', 'change'],
  }],
  password: [{
    validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
      const password = String(value || '')
      if (!password) return callback(new Error(t('platformOps.users.validatePasswordRequired')))
      const valid = password.length >= 8
        && password.length <= 20
        && supportedPasswordPattern.test(password)
        && /[a-z]/.test(password)
        && /[A-Z]/.test(password)
        && /\d/.test(password)
      callback(valid ? undefined : new Error(t('platformOps.users.validatePasswordFormat')))
    },
    trigger: ['blur', 'change'],
  }],
  confirm_password: [{
    validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
      if (!value) return callback(new Error(t('platformOps.users.validateConfirmPasswordRequired')))
      callback(value === createForm.password
        ? undefined
        : new Error(t('platformOps.users.validateConfirmPasswordMismatch')))
    },
    trigger: ['blur', 'change'],
  }],
}))

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
    const data = await listPlatformOpsUsers({
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
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.users.loadFailed')), grouping: true })
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
  filters.account_type = ''
  runFiltersNow()
}

async function openCreate() {
  Object.assign(createForm, {
    email: '',
    first_name: '',
    last_name: '',
    account_type: 'customer',
    organization_name: '',
    password: '',
    confirm_password: '',
    is_active: true,
  })
  createFieldErrors.email = ''
  createFieldErrors.password = ''
  createOpen.value = true
  await nextTick()
  createFormRef.value?.clearValidate()
}

function closeCreate() {
  if (!createBusy.value) createOpen.value = false
}

function applyCreateFieldErrors(error: unknown) {
  const fields = (error as Partial<ApiError> | null)?.fields
  if (!fields) return false
  let applied = false
  for (const field of ['email', 'password'] as const) {
    const message = fields[field]?.[0]
    if (message) {
      createFieldErrors[field] = message
      applied = true
    }
  }
  return applied
}

async function submitCreate() {
  if (createBusy.value) return
  createFieldErrors.email = ''
  createFieldErrors.password = ''
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  createBusy.value = true
  try {
    const user = await createPlatformOpsUser({
      email: createForm.email.trim(),
      first_name: createForm.first_name.trim(),
      last_name: createForm.last_name.trim(),
      password: createForm.password,
      is_active: createForm.is_active,
      is_staff: createForm.account_type === 'administrator',
      organization_name: createForm.account_type === 'customer'
        ? createForm.organization_name.trim()
        : '',
    })
    createOpen.value = false
    ElMessage.success({ message: t('platformOps.users.createSuccess'), grouping: true })
    await router.push(`/platform-ops/users/${user.id}`)
  } catch (error) {
    if (!applyCreateFieldErrors(error)) {
      ElMessage.error({ message: apiErrorMessage(error, t('platformOps.users.createFailed')), grouping: true })
    }
  } finally {
    createBusy.value = false
  }
}

async function toggleUser(row: PlatformOpsUser) {
  if (rowActionId.value) return
  if (row.is_active) {
    deactivateTarget.value = row
    return
  }

  await updateActiveState(row)
}

async function updateActiveState(row: PlatformOpsUser) {
  rowActionId.value = row.id
  try {
    await updatePlatformOpsUser(row.id, { is_active: !row.is_active })
    ElMessage.success({
      message: row.is_active ? t('platformOps.users.deactivateSuccess') : t('platformOps.users.activateSuccess'),
      grouping: true,
    })
    await load()
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.users.saveFailed')), grouping: true })
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

function handleRowAction(command: string, row: PlatformOpsUser) {
  if (command === 'view') void router.push(`/platform-ops/users/${row.id}`)
  if (command === 'toggle') void toggleUser(row)
}

function displayTime(value?: string | null, fallback = '—') {
  return formatLocalDateTime(value, fallback)
}

onMounted(() => {
  void load()
  if (route.query.create === '1') {
    void openCreate()
    void router.replace({ query: {} })
  }
})
watch(() => filters.search, scheduleSearch)
watch(() => [filters.status, filters.account_type], runFiltersNow)
watch(() => [pagination.page, pagination.pageSize], load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="platform-account-page">
      <div class="platform-account-page__lead">
        <p>{{ t('platformOps.users.subtitle') }}</p>
        <el-button type="primary" @click="openCreate">
          {{ t('platformOps.users.create') }}
        </el-button>
      </div>

      <div class="hfl-ops-stats-grid hfl-ops-stats-grid--4">
        <OpsStatCard :label="t('platformOps.users.statTotal')" :value="stats.total" accent="indigo" accent-side="left">
          <template #icon><Users :size="16" /></template>
        </OpsStatCard>
        <OpsStatCard :label="t('platformOps.users.statActive')" :value="stats.active" accent="green" accent-side="left">
          <template #icon><UserCheck :size="16" /></template>
        </OpsStatCard>
        <OpsStatCard :label="t('platformOps.users.statInactive')" :value="stats.inactive" accent="orange" accent-side="left">
          <template #icon><UserX :size="16" /></template>
        </OpsStatCard>
        <OpsStatCard :label="t('platformOps.users.statNeverSignedIn')" :value="stats.never_signed_in" accent="gray" accent-side="left">
          <template #icon><Clock3 :size="16" /></template>
        </OpsStatCard>
      </div>

      <HflTablePanel fill>
        <template #toolbar>
          <div class="platform-account-page__filters">
            <el-input
              v-model="filters.search"
              clearable
              class="platform-account-page__search"
              :placeholder="t('platformOps.users.searchPlaceholder')"
              :aria-label="t('platformOps.users.searchPlaceholder')"
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
              <el-option value="never_signed_in" :label="t('platformOps.users.neverSignedIn')" />
            </el-select>
            <el-select
              v-model="filters.account_type"
              clearable
              class="platform-account-page__filter platform-account-page__filter--wide"
              :placeholder="t('platformOps.users.accountType')"
              :aria-label="t('platformOps.users.accountType')"
            >
              <el-option value="customer" :label="t('platformOps.users.customer')" />
              <el-option value="administrator" :label="t('platformOps.users.administrator')" />
            </el-select>
            <el-button v-if="filters.search || filters.status || filters.account_type" text @click="resetFilters">
              {{ t('platformOps.account.resetFilters') }}
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
            <el-table-column :label="t('platformOps.users.colName')" min-width="210">
              <template #default="{ row }">
                <PlatformOpsUserLink :user-id="row.id" :display-name="row.display_name" />
                <span class="platform-account-page__cell-meta">{{ row.email }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.users.colOrgName')" min-width="190">
              <template #default="{ row }">
                <PlatformOpsOrgLink
                  v-if="row.organization"
                  :org-id="row.organization.id"
                  :org-key="row.organization.key"
                  :label="row.organization.name"
                />
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.users.accountType')" width="160">
              <template #default="{ row }">
                <HflTypeLabel :label="row.is_staff ? t('platformOps.users.administrator') : t('platformOps.users.customer')" />
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.users.colActive')" width="110">
              <template #default="{ row }"><PlatformOpsActiveTag :active="row.is_active" /></template>
            </el-table-column>
            <el-table-column :label="t('platformOps.users.colLastLogin')" width="176">
              <template #default="{ row }">{{ displayTime(row.last_login, t('platformOps.users.never')) }}</template>
            </el-table-column>
            <el-table-column :label="t('platformOps.users.colJoined')" width="176">
              <template #default="{ row }">{{ displayTime(row.date_joined) }}</template>
            </el-table-column>
            <el-table-column width="64" fixed="right" align="center">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="handleRowAction($event, row)">
                  <el-button
                    text
                    class="platform-account-page__row-menu"
                    :loading="rowActionId === row.id"
                    :aria-label="t('platformOps.account.rowActions', { name: row.display_name })"
                  >
                    <MoreHorizontal :size="18" />
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="view">{{ t('platformOps.account.viewDetails') }}</el-dropdown-item>
                      <el-dropdown-item command="toggle">
                        {{ row.is_active ? t('platformOps.users.deactivate') : t('platformOps.users.activate') }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty :description="t('platformOps.users.empty')" :image-size="72" />
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
      v-model="createOpen"
      :size="drawerSize"
      :title="t('platformOps.users.createTitle')"
      :close-on-click-modal="!createBusy"
      :close-on-press-escape="!createBusy"
      :show-close="!createBusy"
      destroy-on-close
      @close="closeCreate"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-position="top"
        class="platform-account-form"
        @submit.prevent="submitCreate"
      >
        <section class="platform-account-form__section">
          <div class="platform-account-form__heading">
            <UserRoundCog :size="17" />
            <div>
              <h3>{{ t('platformOps.users.accountInformation') }}</h3>
              <p>{{ t('platformOps.users.accountInformationHint') }}</p>
            </div>
          </div>
          <el-form-item prop="email" :label="t('platformOps.users.fieldEmail')" :error="createFieldErrors.email">
            <el-input
              v-model="createForm.email"
              type="email"
              autocomplete="off"
              :disabled="createBusy"
              @input="createFieldErrors.email = ''"
            />
          </el-form-item>
          <div class="platform-account-form__grid">
            <el-form-item :label="t('platformOps.users.fieldFirstName')">
              <el-input v-model="createForm.first_name" autocomplete="off" :disabled="createBusy" />
            </el-form-item>
            <el-form-item :label="t('platformOps.users.fieldLastName')">
              <el-input v-model="createForm.last_name" autocomplete="off" :disabled="createBusy" />
            </el-form-item>
          </div>
          <el-form-item :label="t('platformOps.users.accountType')">
            <el-radio-group v-model="createForm.account_type" :disabled="createBusy">
              <el-radio-button value="customer">{{ t('platformOps.users.customer') }}</el-radio-button>
              <el-radio-button value="administrator">{{ t('platformOps.users.administrator') }}</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </section>

        <section v-if="createForm.account_type === 'customer'" class="platform-account-form__section">
          <div class="platform-account-form__heading">
            <Users :size="17" />
            <div>
              <h3>{{ t('platformOps.users.organizationSection') }}</h3>
              <p>{{ t('platformOps.users.createTenantHint') }}</p>
            </div>
          </div>
          <el-form-item :label="t('platformOps.users.organizationName')">
            <el-input
              v-model="createForm.organization_name"
              :placeholder="createForm.email || t('platformOps.users.organizationNamePlaceholder')"
              :disabled="createBusy"
            />
          </el-form-item>
        </section>

        <section class="platform-account-form__section">
          <div class="platform-account-form__heading">
            <UserCheck :size="17" />
            <div>
              <h3>{{ t('platformOps.users.accountSetup') }}</h3>
              <p>{{ t('platformOps.users.accountSetupHint') }}</p>
            </div>
          </div>
          <div class="platform-account-form__grid">
            <el-form-item prop="password" :label="t('platformOps.users.fieldInitialPassword')" :error="createFieldErrors.password">
              <el-input
                v-model="createForm.password"
                type="password"
                show-password
                autocomplete="new-password"
                :disabled="createBusy"
                @input="createFieldErrors.password = ''"
              />
            </el-form-item>
            <el-form-item prop="confirm_password" :label="t('platformOps.users.fieldConfirmPassword')">
              <el-input
                v-model="createForm.confirm_password"
                type="password"
                show-password
                autocomplete="new-password"
                :disabled="createBusy"
              />
            </el-form-item>
          </div>
          <p class="platform-account-form__hint">{{ t('platformOps.users.passwordRequirements') }}</p>
          <el-form-item :label="t('platformOps.users.fieldActive')">
            <el-switch v-model="createForm.is_active" :disabled="createBusy" />
          </el-form-item>
        </section>
      </el-form>
      <template #footer>
        <div class="platform-account-form__footer">
          <el-button :disabled="createBusy" @click="closeCreate">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" :loading="createBusy" @click="submitCreate">
            {{ t('platformOps.users.create') }}
          </el-button>
        </div>
      </template>
    </el-drawer>

    <DangerConfirmDialog
      v-if="deactivateTarget"
      :model-value="true"
      :title="t('platformOps.users.deactivateConfirmTitle')"
      :message="t('platformOps.users.deactivateConfirmMessage', { email: deactivateTarget.email })"
      :warning="t('platformOps.users.deactivateConfirmWarning')"
      :cancel-text="t('common.cancel')"
      :confirm-text="t('platformOps.users.deactivate')"
      :loading="rowActionId === deactivateTarget.id"
      @update:model-value="deactivateTarget = null"
      @confirm="confirmDeactivate"
      @cancel="deactivateTarget = null"
    />
  </ModulePage>
</template>
