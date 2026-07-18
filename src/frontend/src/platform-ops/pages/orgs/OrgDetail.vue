<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import ModulePage from '../../../components/ModulePage.vue'
import PlatformOpsActiveTag from '../../components/PlatformOpsActiveTag.vue'
import PlatformOpsDetailSection from '../../components/PlatformOpsDetailSection.vue'
import PlatformOpsDetailShell from '../../components/PlatformOpsDetailShell.vue'
import PlatformOpsTimeCell from '../../components/PlatformOpsTimeCell.vue'
import PlatformOpsUserLink from '../../components/PlatformOpsUserLink.vue'
import HflPagination from '../../../components/HflPagination.vue'
import { usePlatformOpsClientPagination } from '../../composables/usePlatformOpsClientPagination'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { PLATFORM_OPS_TABLE_HEADER_STYLE } from '../../lib/tableUi'
import {
  endSupportSession,
  fetchOrgSummary,
  startSupportSession,
  updatePlatformOrg,
} from '../../lib/platformOpsApi'
import { getPlatformOpsOrganization } from '../../lib/platformOpsUserApi'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'

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

const orgId = computed(() => Number(route.params.id))
const org = ref<OrgDetail | null>(null)
const summary = ref<Record<string, unknown> | null>(null)
const busy = ref(false)
const saving = ref(false)

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

async function load() {
  if (!orgId.value) {
    router.replace('/platform-ops/orgs')
    return
  }
  busy.value = true
  try {
    org.value = await getPlatformOpsOrganization(orgId.value)
    summary.value = await fetchOrgSummary(orgId.value)
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.orgs.loadFailed')), grouping: true })
    router.replace('/platform-ops/orgs')
  } finally {
    busy.value = false
  }
}

onMounted(load)

async function toggleActive() {
  if (!org.value) return
  saving.value = true
  try {
    org.value = await updatePlatformOrg(org.value.id, { is_active: !org.value.is_active }) as OrgDetail
    ElMessage.success({ message: t('platformOps.orgs.saveSuccess'), grouping: true })
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.orgs.saveFailed')), grouping: true })
  } finally {
    saving.value = false
  }
}

async function enterSupport() {
  if (!org.value) return
  supportBusy.value = true
  try {
    const session = await startSupportSession(org.value.id)
    const base = session.tenant_url?.replace(/\/$/, '') || ''
    const url = `${base}/?org=${encodeURIComponent(session.org_key)}`
    window.open(url, '_blank', 'noopener,noreferrer')
    ElMessage.success({ message: t('platformOps.orgs.supportStarted', { name: session.org_name }), grouping: true })
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.orgs.supportFailed')), grouping: true })
  } finally {
    supportBusy.value = false
  }
}

async function exitSupport() {
  if (!org.value) return
  supportBusy.value = true
  try {
    await endSupportSession(org.value.id)
    ElMessage.success({ message: t('platformOps.orgs.supportEnded'), grouping: true })
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.orgs.supportFailed')), grouping: true })
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
      <template #actions>
        <el-button :loading="supportBusy" @click="enterSupport">{{ t('platformOps.orgs.enterSupport') }}</el-button>
        <el-button :loading="supportBusy" @click="exitSupport">{{ t('platformOps.orgs.exitSupport') }}</el-button>
      </template>

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
              <el-button size="small" class="ml-2" :loading="saving" @click="toggleActive">
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

      <PlatformOpsDetailSection v-if="summary?.counts" :title="t('platformOps.orgs.usageTitle')">
        <div class="hfl-detail-grid">
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colMembers') }}</span>
            <span class="hfl-detail-row__value">{{ (summary.counts as Record<string, number>).members ?? 0 }}</span>
          </div>
          <div class="hfl-detail-row">
            <span class="hfl-detail-row__label">{{ t('platformOps.orgs.colNodes') }}</span>
            <span class="hfl-detail-row__value">{{ (summary.counts as Record<string, number>).nodes ?? 0 }}</span>
          </div>
        </div>
        <div class="platform-ops-detail__links">
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

      <PlatformOpsDetailSection v-if="org?.memberships?.length" :title="t('platformOps.orgs.membersTitle')">
        <div class="platform-ops-detail__table-wrap">
          <el-table
            v-table-column-resize="'platformOps.orgs.members'"
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
          <div class="hfl-list-footer platform-ops-detail__table-footer">
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
  </ModulePage>
</template>
