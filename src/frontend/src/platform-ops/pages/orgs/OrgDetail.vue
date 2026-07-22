<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Building2, CircleGauge, CreditCard, UserRound } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import DangerConfirmDialog from '../../../components/DangerConfirmDialog.vue'
import { usePageRequestScope } from '../../../composables/usePageRequestScope'
import { clearDeployProfileCache, fetchDeployProfile } from '../../../composables/useDeployProfile'
import { apiErrorMessageI18n } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import { notifyError, notifySuccess } from '../../../lib/notify'
import PlatformOpsActiveTag from '../../components/PlatformOpsActiveTag.vue'
import PlatformOpsDetailSection from '../../components/PlatformOpsDetailSection.vue'
import PlatformOpsDetailShell from '../../components/PlatformOpsDetailShell.vue'
import PlatformOpsUserLink from '../../components/PlatformOpsUserLink.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import {
  endSupportSession,
  fetchOrgSummary,
  startSupportSession,
  updatePlatformOrg,
} from '../../lib/platformOpsApi'
import {
  getPlatformOpsOrganization,
  type PlatformOpsOrganization,
} from '../../lib/platformOpsUserApi'

interface QuotaUsage {
  key: string
  limit: number
  used: number
  unit?: string
}

interface OrganizationSummary {
  counts?: {
    nodes?: number
    tasks_running?: number
    tasks_failed?: number
    alerts_firing?: number
  }
  quota_usage?: QuotaUsage[]
  subscription?: {
    plan_name?: string
    status?: string
    ends_at?: string | null
  } | null
  license?: {
    status?: string
    expires_at?: string | null
  } | null
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()
const pageRequests = usePageRequestScope()

const orgId = computed(() => Number(route.params.id))
const org = ref<PlatformOpsOrganization | null>(null)
const summary = ref<OrganizationSummary | null>(null)
const loading = ref(false)
const saving = ref(false)
const summaryLoading = ref(false)
const loadError = ref('')
const summaryError = ref('')
const deactivateConfirmOpen = ref(false)
const supportOrgKey = ref<string | null>(null)
const supportAction = ref<'enter' | 'exit' | null>(null)
const editForm = reactive({ name: '' })

const counts = computed(() => summary.value?.counts || {})
const quotaUsage = computed(() => summary.value?.quota_usage || [])
const isCurrentSupportOrg = computed(() => Boolean(org.value && supportOrgKey.value === org.value.key))
const hasOtherSupportOrg = computed(() => Boolean(
  org.value && supportOrgKey.value && supportOrgKey.value !== org.value.key,
))

function monitoringLink(path: string) {
  const key = org.value?.key
  if (!key) return '/platform-ops/overview'
  const section = path === 'incidents' || path === 'notification-deliveries'
    ? 'alert-center'
    : 'monitoring'
  const destination = path === 'notification-deliveries' ? 'notification-history' : path
  return `/platform-ops/${section}/${destination}?org=${encodeURIComponent(key)}`
}

function quotaPercent(row: QuotaUsage) {
  if (!row.limit || row.limit < 0) return 0
  return Math.min(100, Math.round((Number(row.used || 0) / Number(row.limit)) * 100))
}

async function loadSummary() {
  if (!org.value) return
  const targetOrgId = org.value.id
  const signal = pageRequests.nextSignal('platform-org-summary')
  summaryLoading.value = true
  summaryError.value = ''
  try {
    const result = await fetchOrgSummary(targetOrgId, { signal })
    if (!pageRequests.isCurrentSignal('platform-org-summary', signal)) return
    summary.value = result as OrganizationSummary
  } catch (error) {
    if (pageRequests.isAbortError(error)) return
    summaryError.value = apiErrorMessageI18n(error, t, t('platformOps.orgs.summaryLoadFailed'))
  } finally {
    pageRequests.releaseSignal('platform-org-summary', signal)
    if (!signal.aborted) summaryLoading.value = false
  }
}

async function load() {
  if (!orgId.value) {
    await router.replace('/platform-ops/orgs')
    return
  }
  const targetOrgId = orgId.value
  pageRequests.abortScope('platform-org-summary')
  const signal = pageRequests.nextSignal('platform-org-detail')
  loading.value = true
  loadError.value = ''
  summaryError.value = ''
  org.value = null
  summary.value = null
  try {
    const [result, profile] = await Promise.all([
      getPlatformOpsOrganization(targetOrgId, { signal }),
      fetchDeployProfile(true),
    ])
    if (!pageRequests.isCurrentSignal('platform-org-detail', signal)) return
    org.value = result
    editForm.name = result.name
    supportOrgKey.value = profile?.support_org_key ?? null
    await loadSummary()
  } catch (error) {
    if (pageRequests.isAbortError(error)) return
    loadError.value = apiErrorMessageI18n(error, t, t('platformOps.orgs.loadFailed'))
    notifyError({
      message: loadError.value,
      error,
      showDetails: true,
      dedupeKey: `platform-org:${targetOrgId}:detail-load:error`,
    })
  } finally {
    pageRequests.releaseSignal('platform-org-detail', signal)
    if (!signal.aborted) loading.value = false
  }
}

async function saveOrganization() {
  if (!org.value || saving.value || !editForm.name.trim()) return
  const target = org.value
  saving.value = true
  try {
    org.value = await updatePlatformOrg(target.id, { name: editForm.name.trim() }) as PlatformOpsOrganization
    notifySuccess({
      message: t('platformOps.orgs.saveSuccess'),
      dedupeKey: `platform-org:${target.id}:save`,
    })
  } catch (error) {
    notifyError({
      message: apiErrorMessageI18n(error, t, t('platformOps.orgs.saveFailed')),
      error,
      showDetails: true,
      dedupeKey: `platform-org:${target.id}:save:error`,
    })
  } finally {
    saving.value = false
  }
}

function requestToggleActive() {
  if (!org.value || saving.value) return
  if (org.value.is_active) {
    deactivateConfirmOpen.value = true
    return
  }
  void updateActiveState()
}

async function updateActiveState() {
  if (!org.value || saving.value) return
  const target = org.value
  saving.value = true
  try {
    org.value = await updatePlatformOrg(target.id, { is_active: !target.is_active }) as PlatformOpsOrganization
    deactivateConfirmOpen.value = false
    notifySuccess({
      message: t('platformOps.orgs.saveSuccess'),
      dedupeKey: `platform-org:${target.id}:active:${String(org.value.is_active)}`,
    })
  } catch (error) {
    notifyError({
      message: apiErrorMessageI18n(error, t, t('platformOps.orgs.saveFailed')),
      error,
      showDetails: true,
      dedupeKey: `platform-org:${target.id}:active:error`,
    })
  } finally {
    saving.value = false
  }
}

async function enterSupport() {
  if (!org.value || supportAction.value) return
  const target = org.value
  supportAction.value = 'enter'
  try {
    const session = await startSupportSession(target.id)
    supportOrgKey.value = session.org_key
    clearDeployProfileCache()
    const base = session.tenant_url?.replace(/\/$/, '') || ''
    window.open(`${base}/?org=${encodeURIComponent(session.org_key)}`, '_blank', 'noopener,noreferrer')
    notifySuccess({
      message: t('platformOps.orgs.supportStarted', { name: session.org_name }),
      dedupeKey: `platform-org:${target.id}:support:start:success`,
    })
  } catch (error) {
    notifyError({
      message: apiErrorMessageI18n(error, t, t('platformOps.orgs.supportFailed')),
      error,
      showDetails: true,
      dedupeKey: `platform-org:${target.id}:support:start:error`,
    })
  } finally {
    supportAction.value = null
  }
}

async function exitSupport() {
  if (!org.value || supportAction.value || !isCurrentSupportOrg.value) return
  const target = org.value
  supportAction.value = 'exit'
  try {
    await endSupportSession(target.id)
    supportOrgKey.value = null
    clearDeployProfileCache()
    notifySuccess({
      message: t('platformOps.orgs.supportEnded'),
      dedupeKey: `platform-org:${target.id}:support:end:success`,
    })
  } catch (error) {
    notifyError({
      message: apiErrorMessageI18n(error, t, t('platformOps.orgs.supportFailed')),
      error,
      showDetails: true,
      dedupeKey: `platform-org:${target.id}:support:end:error`,
    })
  } finally {
    supportAction.value = null
  }
}

watch(orgId, () => { void load() }, { immediate: true })
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <PlatformOpsDetailShell
      class="platform-account-detail"
      :title="org?.name || t('platformOps.orgs.detailTitle')"
      :loading="loading"
      @back="router.push('/platform-ops/orgs')"
    >
      <template v-if="org" #status>
        <PlatformOpsActiveTag :active="org.is_active" />
        <span v-if="isCurrentSupportOrg" class="platform-ops-detail__status platform-ops-detail__status--active">
          <span class="platform-ops-detail__status-dot" aria-hidden="true" />
          {{ t('platformOps.orgs.supportActive') }}
        </span>
        <span v-else-if="hasOtherSupportOrg" class="platform-ops-detail__status">
          <span class="platform-ops-detail__status-dot" aria-hidden="true" />
          {{ t('platformOps.orgs.supportActiveFor', { org: supportOrgKey }) }}
        </span>
      </template>
      <template v-if="org" #actions>
        <el-button :loading="saving" @click="requestToggleActive">
          {{ org.is_active ? t('platformOps.orgs.deactivate') : t('platformOps.orgs.activate') }}
        </el-button>
        <el-button
          :loading="supportAction === 'enter'"
          :disabled="Boolean(supportAction)"
          @click="enterSupport"
        >
          {{ isCurrentSupportOrg
            ? t('platformOps.orgs.openSupport')
            : hasOtherSupportOrg
              ? t('platformOps.orgs.switchSupport')
              : t('platformOps.orgs.enterSupport') }}
        </el-button>
        <el-button
          v-if="isCurrentSupportOrg"
          :loading="supportAction === 'exit'"
          :disabled="Boolean(supportAction)"
          @click="exitSupport"
        >
          {{ t('platformOps.orgs.exitSupport') }}
        </el-button>
      </template>

      <el-alert v-if="loadError" type="error" show-icon :closable="false" :title="loadError">
        <template #default><el-button size="small" @click="load">{{ t('common.retry') }}</el-button></template>
      </el-alert>

      <PlatformOpsDetailSection v-if="org" :title="t('platformOps.orgs.sectionBasic')">
        <div class="platform-account-detail__section-lead">
          <Building2 :size="17" aria-hidden="true" />
          <p>{{ t('platformOps.orgs.informationHint') }}</p>
        </div>
        <div class="hfl-detail-grid">
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.organizationId') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ org.id }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colKey') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ org.key }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colName') }}</span>
            <span class="hfl-detail-row__value"><el-input v-model="editForm.name" /></span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colCreated') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ formatLocalDateTime(org.created_at, '—') }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.updatedAt') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ formatLocalDateTime(org.updated_at, '—') }}</span>
          </div>
        </div>
        <div class="platform-ops-detail__footer">
          <el-button type="primary" :loading="saving" @click="saveOrganization">{{ t('common.save') }}</el-button>
        </div>
      </PlatformOpsDetailSection>

      <PlatformOpsDetailSection v-if="org" :title="t('platformOps.orgs.ownerTitle')">
        <div class="platform-account-detail__owner">
          <div class="platform-account-detail__entity">
            <UserRound :size="18" aria-hidden="true" />
            <div>
              <PlatformOpsUserLink
                v-if="org.owner_user_id"
                :user-id="org.owner_user_id"
                :display-name="org.owner_display_name || org.owner_email || '—'"
              />
              <strong v-else>{{ org.owner_display_name || org.owner_email || '—' }}</strong>
              <span>{{ org.owner_email || '—' }}</span>
            </div>
          </div>
          <el-button v-if="org.owner_user_id" @click="router.push(`/platform-ops/users/${org.owner_user_id}`)">
            {{ t('platformOps.orgs.viewUser') }}
          </el-button>
        </div>
      </PlatformOpsDetailSection>

      <PlatformOpsDetailSection v-if="org" :title="t('platformOps.orgs.operationalHealth')">
        <div class="platform-account-detail__section-lead">
          <CircleGauge :size="17" aria-hidden="true" />
          <p>{{ t('platformOps.orgs.operationalHealthHint') }}</p>
        </div>
        <el-alert v-if="summaryError" type="error" show-icon :closable="false" :title="summaryError">
          <template #default><el-button size="small" :loading="summaryLoading" @click="loadSummary">{{ t('common.retry') }}</el-button></template>
        </el-alert>
        <div v-else v-loading="summaryLoading" class="platform-account-detail__metrics platform-account-detail__metrics--large">
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
        <div class="platform-account-detail__links">
          <router-link :to="monitoringLink('incidents')">{{ t('platformOps.orgs.linkAlerts') }}</router-link>
          <router-link :to="monitoringLink('tasks')">{{ t('platformOps.orgs.linkTasks') }}</router-link>
          <router-link :to="monitoringLink('nodes')">{{ t('platformOps.orgs.linkNodes') }}</router-link>
          <router-link :to="monitoringLink('notification-deliveries')">{{ t('platformOps.orgs.linkNotifications') }}</router-link>
        </div>
      </PlatformOpsDetailSection>

      <PlatformOpsDetailSection v-if="org" :title="t('platformOps.orgs.subscriptionUsage')">
        <div class="platform-account-detail__section-lead">
          <CreditCard :size="17" aria-hidden="true" />
          <p>{{ t('platformOps.orgs.subscriptionUsageHint') }}</p>
        </div>
        <div v-loading="summaryLoading" class="hfl-detail-grid">
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.plan') }}</span>
            <span class="hfl-detail-row__value">{{ summary?.subscription?.plan_name || '—' }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.subscriptionStatus') }}</span>
            <span class="hfl-detail-row__value">{{ summary?.subscription?.status || '—' }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.licenseStatus') }}</span>
            <span class="hfl-detail-row__value">{{ summary?.license?.status || '—' }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.expiresAt') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">
              {{ formatLocalDateTime(summary?.license?.expires_at || summary?.subscription?.ends_at, '—') }}
            </span>
          </div>
        </div>
        <div v-if="quotaUsage.length" class="platform-account-detail__quotas">
          <div v-for="quota in quotaUsage" :key="`${quota.key}:${quota.unit || ''}`" class="platform-account-detail__quota">
            <div><span>{{ quota.key }}</span><strong>{{ quota.used }} / {{ quota.limit }} {{ quota.unit || '' }}</strong></div>
            <el-progress :percentage="quotaPercent(quota)" :stroke-width="7" :show-text="false" />
          </div>
        </div>
      </PlatformOpsDetailSection>
    </PlatformOpsDetailShell>

    <DangerConfirmDialog
      v-if="org"
      v-model="deactivateConfirmOpen"
      :title="t('platformOps.orgs.deactivateConfirmTitle')"
      :message="t('platformOps.orgs.deactivateConfirmMessage', { name: org.name })"
      :warning="t('platformOps.orgs.deactivateConfirmWarning')"
      :cancel-text="t('common.cancel')"
      :confirm-text="t('platformOps.orgs.deactivateConfirmAction')"
      :loading="saving"
      @confirm="updateActiveState"
    />
  </ModulePage>
</template>
