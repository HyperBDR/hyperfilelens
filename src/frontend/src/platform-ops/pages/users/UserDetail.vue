<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import ModulePage from '../../../components/ModulePage.vue'
import PlatformOpsActiveTag from '../../components/PlatformOpsActiveTag.vue'
import PlatformOpsDetailSection from '../../components/PlatformOpsDetailSection.vue'
import PlatformOpsDetailShell from '../../components/PlatformOpsDetailShell.vue'
import HflPagination from '../../../components/HflPagination.vue'
import { usePlatformOpsClientPagination } from '../../composables/usePlatformOpsClientPagination'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { PLATFORM_OPS_TABLE_HEADER_STYLE } from '../../lib/tableUi'
import {
  getPlatformOpsUser,
  resetPlatformOpsUserPassword,
  updatePlatformOpsUser,
  type PlatformOpsUser,
} from '../../lib/platformOpsUserApi'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()

const userId = computed(() => Number(route.params.id))
const user = ref<PlatformOpsUser | null>(null)
const busy = ref(false)
const saving = ref(false)

const editForm = ref({
  email: '',
  first_name: '',
  last_name: '',
  is_active: true,
  is_staff: false,
})

const memberships = computed(() => user.value?.memberships || [])
const {
  currentPage: membershipsPage,
  pageSize: membershipsPageSize,
  totalCount: membershipsTotal,
  pagedRows: pagedMemberships,
} = usePlatformOpsClientPagination(memberships)

async function load() {
  if (!userId.value) {
    router.replace('/platform-ops/users')
    return
  }
  busy.value = true
  try {
    const data = await getPlatformOpsUser(userId.value)
    user.value = data
    editForm.value = {
      email: data.email,
      first_name: data.first_name || '',
      last_name: data.last_name || '',
      is_active: data.is_active,
      is_staff: data.is_staff,
    }
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.users.loadFailed')), grouping: true })
    router.replace('/platform-ops/users')
  } finally {
    busy.value = false
  }
}

async function save() {
  if (!user.value) return
  saving.value = true
  try {
    user.value = await updatePlatformOpsUser(user.value.id, editForm.value)
    ElMessage.success({ message: t('platformOps.users.saveSuccess'), grouping: true })
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.users.saveFailed')), grouping: true })
  } finally {
    saving.value = false
  }
}

async function promptResetPassword() {
  if (!user.value) return
  try {
    const { value } = await ElMessageBox.prompt(
      t('platformOps.users.resetPasswordHint'),
      t('platformOps.users.resetPassword'),
      {
        inputType: 'password',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      },
    )
    if (!value?.trim()) return
    await resetPlatformOpsUserPassword(user.value.id, value.trim())
    ElMessage.success({ message: t('platformOps.users.resetPasswordSuccess'), grouping: true })
  } catch (err) {
    if (err === 'cancel') return
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.users.resetPasswordFailed')), grouping: true })
  }
}

onMounted(load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <PlatformOpsDetailShell
      :title="user?.display_name || t('platformOps.users.detailTitle')"
      :loading="busy"
      @back="router.push('/platform-ops/users')"
    >
      <PlatformOpsDetailSection v-if="user" :title="t('platformOps.users.sectionBasic')">
        <div class="hfl-detail-grid">
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.fieldEmail') }}</span>
            <span class="hfl-detail-row__value">
              <el-input v-model="editForm.email" class="hfl-detail-form-input" />
            </span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.fieldFirstName') }}</span>
            <span class="hfl-detail-row__value">
              <el-input v-model="editForm.first_name" class="hfl-detail-form-input" />
            </span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.fieldLastName') }}</span>
            <span class="hfl-detail-row__value">
              <el-input v-model="editForm.last_name" class="hfl-detail-form-input" />
            </span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.fieldActive') }}</span>
            <span class="hfl-detail-row__value">
              <el-switch v-model="editForm.is_active" />
            </span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.fieldStaff') }}</span>
            <span class="hfl-detail-row__value">
              <el-switch v-model="editForm.is_staff" />
            </span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.colJoined') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">
              {{ formatLocalDateTime(user.date_joined, '—') }}
            </span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.colLastLogin') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">
              {{ formatLocalDateTime(user.last_login, '—') }}
            </span>
          </div>
        </div>
        <div class="platform-ops-detail__footer">
          <el-button type="primary" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
          <el-button @click="promptResetPassword">{{ t('platformOps.users.resetPassword') }}</el-button>
        </div>
      </PlatformOpsDetailSection>

      <PlatformOpsDetailSection v-if="user?.memberships?.length" :title="t('platformOps.users.membershipsTitle')">
        <div class="platform-ops-detail__table-wrap">
          <el-table
            v-table-column-resize="'platformOps.users.memberships'"
            :data="pagedMemberships"
            stripe
            class="hfl-list-table"
            :header-cell-style="PLATFORM_OPS_TABLE_HEADER_STYLE"
          >
            <el-table-column prop="organization_name" :label="t('platformOps.users.colOrgName')" min-width="160" />
            <el-table-column prop="organization_key" :label="t('platformOps.users.colOrgKey')" min-width="140" />
            <el-table-column prop="role" :label="t('platformOps.users.colOrgRole')" min-width="120" />
            <el-table-column :label="t('platformOps.users.colActive')" min-width="110" align="center">
              <template #default="{ row }">
                <PlatformOpsActiveTag :active="row.is_active" />
              </template>
            </el-table-column>
          </el-table>
          <div class="hfl-list-footer platform-ops-detail__table-footer">
            <HflPagination
              v-model:current-page="membershipsPage"
              v-model:page-size="membershipsPageSize"
              class="hfl-list-footer__pagination"
              :total="membershipsTotal"
            />
          </div>
        </div>
      </PlatformOpsDetailSection>
    </PlatformOpsDetailShell>
  </ModulePage>
</template>
