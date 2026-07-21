<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ModulePage from '../../../components/ModulePage.vue'
import DangerConfirmDialog from '../../../components/DangerConfirmDialog.vue'
import PlatformOpsActiveTag from '../../components/PlatformOpsActiveTag.vue'
import PlatformOpsDetailSection from '../../components/PlatformOpsDetailSection.vue'
import PlatformOpsDetailShell from '../../components/PlatformOpsDetailShell.vue'
import PlatformOpsTimeCell from '../../components/PlatformOpsTimeCell.vue'
import PlatformOpsUserLink from '../../components/PlatformOpsUserLink.vue'
import HflPagination from '../../../components/HflPagination.vue'
import { usePlatformOpsClientPagination } from '../../composables/usePlatformOpsClientPagination'
import { usePageRequestScope } from '../../../composables/usePageRequestScope'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { PLATFORM_OPS_TABLE_HEADER_STYLE } from '../../lib/tableUi'
import {
  endSupportSession,
  fetchOrgSummary,
  startSupportSession,
  updatePlatformOrg,
} from '../../lib/platformOpsApi'
import { getPlatformOpsOrganization } from '../../lib/platformOpsUserApi'
import { apiErrorMessageI18n } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import { notifyError, notifySuccess } from '../../../lib/notify'

interface OrgDetail {
  id: number
  key: string
  name: string
  is_active: boolean
  owner_email?: string | null
  member_count?: number
  created_at?: string | null
  memberships?: Array<{
    id: number
    user_id: number
    user_email: string
    user_display_name: string
    role: string
    is_active: boolean
    created_at?: string
  }>
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const sideNav = usePlatformOpsSideNav()
const pageRequests = usePageRequestScope()

const orgId = computed(() => Number(route.params.id))
const org = ref<OrgDetail | null>(null)
const summary = ref<Record<string, unknown> | null>(null)
const busy = ref(false)
const saving = ref(false)
const loadError = ref('')
const summaryError = ref('')
const summaryBusy = ref(false)
const deactivateConfirmOpen = ref(false)

const memberships = computed(() => org.value?.memberships || [])
const {
  currentPage: membersPage,
  pageSize: membersPageSize,
  totalCount: membersTotal,
  pagedRows: pagedMembers,
} = usePlatformOpsClientPagination(memberships)
const supportBusy = ref(false)

const monitoringLinks = computed(() => {
  const key = org.value?.key
  if (!key) return []
  const q = encodeURIComponent(key)
  return [
    { label: t('platformOps.orgs.linkTasks'), to: `/platform-ops/monitoring/tasks?org=${q}` },
    { label: t('platformOps.orgs.linkNodes'), to: `/platform-ops/monitoring/nodes?org=${q}` },
  ]
})

async function loadSummary() {
  if (!org.value) return
  const targetOrgId = org.value.id
  const signal = pageRequests.nextSignal('platform-org-summary')
  summaryBusy.value = true
  summaryError.value = ''
  try {
    const result = await fetchOrgSummary(targetOrgId, { signal })
    if (!pageRequests.isCurrentSignal('platform-org-summary', signal)) return
    summary.value = result
  } catch (err) {
    if (pageRequests.isAbortError(err)) return
    summaryError.value = apiErrorMessageI18n(err, t, t('platformOps.orgs.summaryLoadFailed'))
    notifyError({
      message: summaryError.value,
      error: err,
      showDetails: true,
      dedupeKey: `platform-org:${targetOrgId}:summary-load:error`,
    })
  } finally {
    pageRequests.releaseSignal('platform-org-summary', signal)
    if (!signal.aborted) summaryBusy.value = false
  }
}

async function load() {
  if (!orgId.value) {
    router.replace('/platform-ops/orgs')
    return
  }
  const targetOrgId = orgId.value
  pageRequests.abortScope('platform-org-summary')
  summaryBusy.value = false
  const signal = pageRequests.nextSignal('platform-org-detail')
  busy.value = true
  loadError.value = ''
  summaryError.value = ''
  org.value = null
  summary.value = null
  try {
    const result = await getPlatformOpsOrganization(targetOrgId, { signal })
    if (!pageRequests.isCurrentSignal('platform-org-detail', signal)) return
    org.value = result as OrgDetail
    await loadSummary()
  } catch (err) {
    if (pageRequests.isAbortError(err)) return
    loadError.value = apiErrorMessageI18n(err, t, t('platformOps.orgs.loadFailed'))
    notifyError({
      message: loadError.value,
      error: err,
      showDetails: true,
      dedupeKey: `platform-org:${targetOrgId}:detail-load:error`,
    })
  } finally {
    pageRequests.releaseSignal('platform-org-detail', signal)
    if (!signal.aborted) busy.value = false
  }
}

watch(orgId, () => {
  void load()
}, { immediate: true })

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
  const targetOrg = org.value
  saving.value = true
  try {
    org.value = await updatePlatformOrg(targetOrg.id, { is_active: !targetOrg.is_active }) as OrgDetail
    deactivateConfirmOpen.value = false
    notifySuccess({
      message: t('platformOps.orgs.saveSuccess'),
      dedupeKey: `platform-org:${targetOrg.id}:active:${String(org.value.is_active)}`,
    })
  } catch (err) {
    const message = apiErrorMessageI18n(err, t, t('platformOps.orgs.saveFailed'))
    notifyError({
      message,
      error: err,
      showDetails: true,
      dedupeKey: `platform-org:${targetOrg.id}:active:error`,
    })
  } finally {
    saving.value = false
  }
}

async function enterSupport() {
  if (!org.value || supportBusy.value) return
  const targetOrg = org.value
  supportBusy.value = true
  try {
    const session = await startSupportSession(targetOrg.id)
    const base = session.tenant_url?.replace(/\/$/, '') || ''
    const url = `${base}/?org=${encodeURIComponent(session.org_key)}`
    window.open(url, '_blank', 'noopener,noreferrer')
    notifySuccess({
      message: t('platformOps.orgs.supportStarted', { name: session.org_name }),
      dedupeKey: `platform-org:${targetOrg.id}:support:start:success`,
    })
  } catch (err) {
    const message = apiErrorMessageI18n(err, t, t('platformOps.orgs.supportFailed'))
    notifyError({
      message,
      error: err,
      showDetails: true,
      dedupeKey: `platform-org:${targetOrg.id}:support:start:error`,
    })
  } finally {
    supportBusy.value = false
  }
}

async function exitSupport() {
  if (!org.value || supportBusy.value) return
  const targetOrg = org.value
  supportBusy.value = true
  try {
    await endSupportSession(targetOrg.id)
    notifySuccess({
      message: t('platformOps.orgs.supportEnded'),
      dedupeKey: `platform-org:${targetOrg.id}:support:end:success`,
    })
  } catch (err) {
    const message = apiErrorMessageI18n(err, t, t('platformOps.orgs.supportFailed'))
    notifyError({
      message,
      error: err,
      showDetails: true,
      dedupeKey: `platform-org:${targetOrg.id}:support:end:error`,
    })
  } finally {
    supportBusy.value = false
  }
}
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <PlatformOpsDetailShell
      :title="org?.name || t('platformOps.orgs.detailTitle')"
      :loading="busy"
      @back="router.push('/platform-ops/orgs')"
    >
      <template v-if="org" #actions>
        <el-button :loading="supportBusy" @click="enterSupport">{{ t('platformOps.orgs.enterSupport') }}</el-button>
        <el-button :loading="supportBusy" @click="exitSupport">{{ t('platformOps.orgs.exitSupport') }}</el-button>
      </template>

      <el-alert
        v-if="loadError"
        type="error"
        show-icon
        :closable="false"
        :title="loadError"
      >
        <template #default>
          <el-button size="small" @click="load">
            {{ t('common.retry') }}
          </el-button>
        </template>
      </el-alert>

      <PlatformOpsDetailSection v-if="org" :title="t('platformOps.orgs.sectionBasic')">
        <div class="hfl-detail-grid">
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colKey') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ org.key }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colName') }}</span>
            <span class="hfl-detail-row__value">{{ org.name }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colOwner') }}</span>
            <span class="hfl-detail-row__value">{{ org.owner_email || '—' }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colMembers') }}</span>
            <span class="hfl-detail-row__value">{{ org.member_count ?? 0 }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colActive') }}</span>
            <span class="hfl-detail-row__value">
              <PlatformOpsActiveTag :active="org.is_active" />
              <el-button size="small" class="ml-2" :loading="saving" @click="requestToggleActive">
                {{ org.is_active ? t('platformOps.orgs.deactivate') : t('platformOps.orgs.activate') }}
              </el-button>
            </span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colCreated') }}</span>
            <span class="hfl-detail-row__value hfl-detail-row__value--mono">
              {{ formatLocalDateTime(org.created_at, '—') }}
            </span>
          </div>
        </div>
      </PlatformOpsDetailSection>

      <PlatformOpsDetailSection v-if="org" :title="t('platformOps.orgs.usageTitle')">
        <el-alert
          v-if="summaryError"
          type="error"
          show-icon
          :closable="false"
          :title="summaryError"
        >
          <template #default>
            <el-button size="small" :loading="summaryBusy" @click="loadSummary">
              {{ t('common.retry') }}
            </el-button>
          </template>
        </el-alert>
        <div v-else-if="summary?.counts" v-loading="summaryBusy" class="hfl-detail-grid">
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colMembers') }}</span>
            <span class="hfl-detail-row__value">{{ (summary.counts as Record<string, number>).members ?? 0 }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colNodes') }}</span>
            <span class="hfl-detail-row__value">{{ (summary.counts as Record<string, number>).nodes ?? 0 }}</span>
          </div>
        </div>
        <div v-else v-loading="summaryBusy" class="platform-ops-detail__summary-state">
          <span v-if="!summaryBusy">{{ t('common.empty') }}</span>
        </div>
        <div v-if="summary?.counts" class="platform-ops-detail__links">
          <router-link
            v-for="link in monitoringLinks"
            :key="link.to"
            :to="link.to"
            class="platform-ops-detail__link"
          >
            {{ link.label }}
          </router-link>
        </div>
      </PlatformOpsDetailSection>

      <PlatformOpsDetailSection v-if="org" :title="t('platformOps.orgs.membersTitle')">
        <div class="platform-ops-detail__table-wrap">
          <el-table
            v-if="memberships.length"
            v-table-column-resize="'platformOps.orgs.members'"
            v-table-overflow-title
            :data="pagedMembers"
            stripe
            class="hfl-list-table"
            :header-cell-style="PLATFORM_OPS_TABLE_HEADER_STYLE"
          >
            <el-table-column :label="t('platformOps.users.colName')" min-width="160">
              <template #default="{ row }">
                <PlatformOpsUserLink :user-id="row.user_id" :display-name="row.user_display_name" />
              </template>
            </el-table-column>
            <el-table-column prop="user_email" :label="t('platformOps.users.colEmail')" min-width="200" />
            <el-table-column prop="role" :label="t('platformOps.users.colOrgRole')" min-width="120" />
            <el-table-column :label="t('platformOps.users.colActive')" min-width="110" align="center">
              <template #default="{ row }">
                <PlatformOpsActiveTag :active="row.is_active" />
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.users.colJoined')" min-width="170">
              <template #default="{ row }">
                <PlatformOpsTimeCell :value="row.created_at" />
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else :description="t('platformOps.orgs.membersEmpty')" :image-size="72" />
          <div v-if="memberships.length" class="hfl-list-footer platform-ops-detail__table-footer">
            <HflPagination
              v-model:current-page="membersPage"
              v-model:page-size="membersPageSize"
              class="hfl-list-footer__pagination"
              :total="membersTotal"
            />
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
