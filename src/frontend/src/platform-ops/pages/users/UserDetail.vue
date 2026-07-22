<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Activity, Building2, KeyRound, UserRound } from 'lucide-vue-next'
import DangerConfirmDialog from '../../../components/DangerConfirmDialog.vue'
import HflTypeLabel from '../../../components/HflTypeLabel.vue'
import ModulePage from '../../../components/ModulePage.vue'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsActiveTag from '../../components/PlatformOpsActiveTag.vue'
import PlatformOpsDetailSection from '../../components/PlatformOpsDetailSection.vue'
import PlatformOpsDetailShell from '../../components/PlatformOpsDetailShell.vue'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { fetchOrgSummary } from '../../lib/platformOpsApi'
import {
  getPlatformOpsUser,
  resetPlatformOpsUserPassword,
  updatePlatformOpsUser,
  type PlatformOpsUser,
} from '../../lib/platformOpsUserApi'

interface OrganizationSummary {
  counts?: {
    nodes?: number
    tasks_running?: number
    tasks_failed?: number
    alerts_firing?: number
  }
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()

const userId = computed(() => Number(route.params.id))
const user = ref<PlatformOpsUser | null>(null)
const summary = ref<OrganizationSummary | null>(null)
const loading = ref(false)
const summaryLoading = ref(false)
const saving = ref(false)
const statusBusy = ref(false)
const deactivateConfirmOpen = ref(false)
const editForm = reactive({ email: '', first_name: '', last_name: '' })

const accountTypeLabel = computed(() => (
  user.value?.is_staff ? t('platformOps.users.administrator') : t('platformOps.users.customer')
))
const counts = computed(() => summary.value?.counts || {})

async function loadSummary() {
  const organization = user.value?.organization
  if (!organization) {
    summary.value = null
    return
  }
  summaryLoading.value = true
  try {
    summary.value = await fetchOrgSummary(organization.id) as OrganizationSummary
  } catch {
    summary.value = null
  } finally {
    summaryLoading.value = false
  }
}

async function load() {
  if (!userId.value) {
    await router.replace('/platform-ops/users')
    return
  }
  loading.value = true
  try {
    const data = await getPlatformOpsUser(userId.value)
    user.value = data
    Object.assign(editForm, {
      email: data.email,
      first_name: data.first_name || '',
      last_name: data.last_name || '',
    })
    await loadSummary()
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.users.loadFailed')), grouping: true })
    await router.replace('/platform-ops/users')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!user.value || saving.value) return
  saving.value = true
  try {
    user.value = await updatePlatformOpsUser(user.value.id, {
      email: editForm.email.trim(),
      first_name: editForm.first_name.trim(),
      last_name: editForm.last_name.trim(),
    })
    ElMessage.success({ message: t('platformOps.users.saveSuccess'), grouping: true })
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.users.saveFailed')), grouping: true })
  } finally {
    saving.value = false
  }
}

async function toggleActive() {
  if (!user.value || statusBusy.value) return
  if (user.value.is_active) {
    deactivateConfirmOpen.value = true
    return
  }

  await updateActiveState()
}

async function updateActiveState() {
  if (!user.value || statusBusy.value) return
  const target = user.value
  statusBusy.value = true
  try {
    user.value = await updatePlatformOpsUser(target.id, { is_active: !target.is_active })
    ElMessage.success({
      message: target.is_active ? t('platformOps.users.deactivateSuccess') : t('platformOps.users.activateSuccess'),
      grouping: true,
    })
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.users.saveFailed')), grouping: true })
  } finally {
    statusBusy.value = false
    deactivateConfirmOpen.value = false
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
  } catch (error) {
    if (error === 'cancel') return
    ElMessage.error({ message: apiErrorMessage(error, t('platformOps.users.resetPasswordFailed')), grouping: true })
  }
}

function monitoringLink(path: string) {
  const key = user.value?.organization?.key
  if (!key) return '/platform-ops/overview'
  const section = path === 'incidents' || path === 'notification-deliveries'
    ? 'alert-center'
    : 'monitoring'
  const destination = path === 'notification-deliveries' ? 'notification-history' : path
  return `/platform-ops/${section}/${destination}?org=${encodeURIComponent(key)}`
}

onMounted(load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <PlatformOpsDetailShell
      class="platform-account-detail"
      :title="user?.display_name || t('platformOps.users.detailTitle')"
      :loading="loading"
      @back="router.push('/platform-ops/users')"
    >
      <template v-if="user" #status>
        <PlatformOpsActiveTag :active="user.is_active" />
        <HflTypeLabel :label="accountTypeLabel" />
      </template>
      <template v-if="user" #actions>
        <el-button :loading="statusBusy" @click="toggleActive">
          {{ user.is_active ? t('platformOps.users.deactivate') : t('platformOps.users.activate') }}
        </el-button>
      </template>

      <PlatformOpsDetailSection v-if="user" :title="t('platformOps.users.accountInformation')">
        <div class="platform-account-detail__section-lead">
          <UserRound :size="17" aria-hidden="true" />
          <p>{{ t('platformOps.users.accountInformationHint') }}</p>
        </div>
        <div class="hfl-detail-grid">
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.userId') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ user.id }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.accountType') }}</span>
            <span class="hfl-detail-row__value">{{ accountTypeLabel }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.fieldEmail') }}</span>
            <span class="hfl-detail-row__value"><el-input v-model="editForm.email" type="email" /></span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.fieldFirstName') }}</span>
            <span class="hfl-detail-row__value"><el-input v-model="editForm.first_name" /></span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.fieldLastName') }}</span>
            <span class="hfl-detail-row__value"><el-input v-model="editForm.last_name" /></span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.colJoined') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ formatLocalDateTime(user.date_joined, '—') }}</span>
          </div>
        </div>
        <div class="platform-ops-detail__footer">
          <el-button type="primary" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
        </div>
      </PlatformOpsDetailSection>

      <PlatformOpsDetailSection v-if="user && !user.is_staff" :title="t('platformOps.users.organizationSection')">
        <div v-if="user.organization" v-loading="summaryLoading" class="platform-account-detail__organization">
          <div class="platform-account-detail__organization-head">
            <div class="platform-account-detail__entity">
              <Building2 :size="18" aria-hidden="true" />
              <div>
                <PlatformOpsOrgLink
                  :org-id="user.organization.id"
                  :org-key="user.organization.key"
                  :label="user.organization.name"
                />
                <span>{{ user.organization.key }}</span>
              </div>
            </div>
            <PlatformOpsActiveTag :active="user.organization.is_active" />
          </div>
          <div class="platform-account-detail__metrics">
            <router-link :to="monitoringLink('nodes')">
              <span>{{ t('platformOps.orgs.colNodes') }}</span><strong>{{ counts.nodes || 0 }}</strong>
            </router-link>
            <router-link :to="monitoringLink('tasks')">
              <span>{{ t('platformOps.monitoring.runningTasks') }}</span><strong>{{ counts.tasks_running || 0 }}</strong>
            </router-link>
            <router-link :to="monitoringLink('tasks')" :class="{ 'is-attention': (counts.tasks_failed || 0) > 0 }">
              <span>{{ t('platformOps.monitoring.failedTasks') }}</span><strong>{{ counts.tasks_failed || 0 }}</strong>
            </router-link>
            <router-link :to="monitoringLink('incidents')" :class="{ 'is-attention': (counts.alerts_firing || 0) > 0 }">
              <span>{{ t('platformOps.overview.firingIncidents') }}</span><strong>{{ counts.alerts_firing || 0 }}</strong>
            </router-link>
          </div>
        </div>
        <el-empty v-else :description="t('platformOps.users.noOrganization')" :image-size="72" />
      </PlatformOpsDetailSection>

      <PlatformOpsDetailSection v-if="user" :title="t('platformOps.users.authentication')">
        <div class="platform-account-detail__section-lead">
          <KeyRound :size="17" aria-hidden="true" />
          <p>{{ t('platformOps.users.authenticationHint') }}</p>
        </div>
        <div class="hfl-detail-grid">
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.passwordStatus') }}</span>
            <span class="hfl-detail-row__value">
              {{ user.has_usable_password ? t('platformOps.users.passwordConfigured') : t('platformOps.users.externalSignIn') }}
            </span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.colLastLogin') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ formatLocalDateTime(user.last_login, t('platformOps.users.never')) }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.lastLoginIp') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ user.last_login_ip || '—' }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.users.registeredAt') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ formatLocalDateTime(user.registered_at, '—') }}</span>
          </div>
        </div>
        <div class="platform-ops-detail__footer">
          <el-button @click="promptResetPassword">{{ t('platformOps.users.resetPassword') }}</el-button>
        </div>
      </PlatformOpsDetailSection>

      <PlatformOpsDetailSection v-if="user?.organization" :title="t('platformOps.users.operationalActivity')">
        <div class="platform-account-detail__section-lead">
          <Activity :size="17" aria-hidden="true" />
          <p>{{ t('platformOps.users.operationalActivityHint') }}</p>
        </div>
        <div class="platform-account-detail__links">
          <router-link :to="monitoringLink('incidents')">{{ t('platformOps.orgs.linkAlerts') }}</router-link>
          <router-link :to="monitoringLink('tasks')">{{ t('platformOps.orgs.linkTasks') }}</router-link>
          <router-link :to="monitoringLink('nodes')">{{ t('platformOps.orgs.linkNodes') }}</router-link>
          <router-link :to="monitoringLink('notification-deliveries')">{{ t('platformOps.orgs.linkNotifications') }}</router-link>
        </div>
      </PlatformOpsDetailSection>
    </PlatformOpsDetailShell>

    <DangerConfirmDialog
      v-if="user"
      v-model="deactivateConfirmOpen"
      :title="t('platformOps.users.deactivateConfirmTitle')"
      :message="t('platformOps.users.deactivateConfirmMessage', { email: user.email })"
      :warning="t('platformOps.users.deactivateConfirmWarning')"
      :cancel-text="t('common.cancel')"
      :confirm-text="t('platformOps.users.deactivate')"
      :loading="statusBusy"
      @confirm="updateActiveState"
    />
  </ModulePage>
</template>
