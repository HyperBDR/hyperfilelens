<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus, RefreshCw } from 'lucide-vue-next'
import { api, apiErrorMessageI18n } from '../../lib/api'
import { formatLocalDateTime } from '../../lib/dateTime'
import { asList, asPagination, unwrapApiPayload } from '../../lib/parse'
import { notifyError, notifySuccess, notifyWarning } from '../../lib/notify'
import Modal from '../../components/Modal.vue'
import ModulePage from '../../components/ModulePage.vue'
import HflPagination from '../../components/HflPagination.vue'
import HflTablePanel from '../../components/HflTablePanel.vue'
import { usePageRequestScope } from '../../composables/usePageRequestScope'
import { useProtectionSideNav } from '../../composables/useProtectionSideNav'
import { booleanStatusTag } from '../../lib/statusTag'

type RetentionRule = {
  id: number
  organization: number
  name: string
  spec: unknown
  is_active: boolean
  updated_at?: string
}

type RetentionSpecItem = {
  key: string
  label: string
  value: string
}

const { t } = useI18n()
const protectionMenus = useProtectionSideNav()
const pageRequests = usePageRequestScope()

const rows = ref<RetentionRule[]>([])
const loading = ref(false)
const saving = ref(false)
const listError = ref('')
const open = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const form = reactive({ organization: '', name: '' })
const formErrors = reactive({ organization: '', name: '' })

const specLabelKeys: Record<string, string> = {
  latest: 'protection.retentionPage.specLatest',
  hourly: 'protection.retentionPage.specHourly',
  daily: 'protection.retentionPage.specDaily',
  weekly: 'protection.retentionPage.specWeekly',
  monthly: 'protection.retentionPage.specMonthly',
  yearly: 'protection.retentionPage.specYearly',
  annual: 'protection.retentionPage.specYearly',
}

function formatDate(value?: string | null) {
  return formatLocalDateTime(value, '--')
}

function formatSpecLabel(key: string) {
  const labelKey = specLabelKeys[key]
  if (labelKey) return t(labelKey)
  return key
    .replace(/_/g, ' ')
    .replace(/^./, (character) => character.toUpperCase())
}

function formatSpecValue(value: unknown): string {
  if (value === undefined || value === null || value === '') {
    return t('protection.retentionPage.specUnknownValue')
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatSpecValue(item)).join(', ')
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${formatSpecLabel(key)}: ${formatSpecValue(item)}`)
      .join('; ')
  }
  return String(value)
}

function retentionSpecItems(spec: unknown): RetentionSpecItem[] {
  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) return []
  return Object.entries(spec as Record<string, unknown>).map(([key, value]) => ({
    key,
    label: formatSpecLabel(key),
    value: formatSpecValue(value),
  }))
}

function responseTotal(data: unknown, rowCount: number) {
  const payload = unwrapApiPayload<Record<string, unknown>>(data)
  const pagination = asPagination(data)
  const count = Number(payload?.count ?? pagination?.total)
  return Number.isFinite(count) && count >= 0 ? count : rowCount
}

async function load() {
  const signal = pageRequests.nextSignal('retention-list')
  loading.value = true
  listError.value = ''
  try {
    const query = new URLSearchParams({
      page: String(currentPage.value),
      page_size: String(pageSize.value),
      ordering: '-updated_at',
    })
    const data = await api<unknown>(`/api/v1/protection/retention-rules/?${query}`, { signal })
    if (!pageRequests.isCurrentSignal('retention-list', signal)) return
    const nextRows = asList<RetentionRule>(data)
    rows.value = nextRows
    total.value = responseTotal(data, nextRows.length)
  } catch (error) {
    if (pageRequests.isAbortError(error)) return
    listError.value = apiErrorMessageI18n(error, t, t('protection.retentionPage.loadFailed'))
  } finally {
    pageRequests.releaseSignal('retention-list', signal)
    if (!signal.aborted) loading.value = false
  }
}

function resetForm() {
  form.organization = ''
  form.name = ''
  formErrors.organization = ''
  formErrors.name = ''
}

function openCreate() {
  resetForm()
  open.value = true
}

function validateForm() {
  const organization = Number(form.organization)
  formErrors.organization = Number.isInteger(organization) && organization > 0
    ? ''
    : t('protection.retentionPage.validateOrgRequired')
  formErrors.name = form.name.trim()
    ? ''
    : t('protection.retentionPage.validateNameRequired')
  return !formErrors.organization && !formErrors.name
}

async function save() {
  if (saving.value) return
  if (!validateForm()) {
    notifyWarning({
      message: formErrors.organization || formErrors.name,
      dedupeKey: 'retention-rule:create:validation',
    })
    return
  }

  saving.value = true
  try {
    await api(`/api/v1/protection/retention-rules/`, {
      method: 'POST',
      body: JSON.stringify({
        organization: Number(form.organization),
        name: form.name.trim(),
        spec: {
          latest: 10,
          hourly: 24,
          daily: 7,
          weekly: 4,
          monthly: 12,
          yearly: 3,
        },
        is_active: true,
      }),
    })
    open.value = false
    notifySuccess({
      message: t('protection.retentionPage.saveSuccess'),
      dedupeKey: 'retention-rule:create:success',
    })
    if (currentPage.value === 1) {
      await load()
    } else {
      currentPage.value = 1
    }
  } catch (error) {
    const message = apiErrorMessageI18n(error, t, t('protection.retentionPage.saveFailed'))
    notifyError({
      message,
      error,
      showDetails: true,
      dedupeKey: 'retention-rule:create:error',
    })
  } finally {
    saving.value = false
  }
}

watch([currentPage, pageSize], () => {
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <ModulePage
    :title="t('protection.side.retention')"
    :menus="protectionMenus"
    body-fill
  >
    <HflTablePanel fill>
      <template #toolbar>
        <ElButton type="primary" @click="openCreate">
          <Plus :size="16" />
          {{ t('protection.retentionPage.btnNewRule') }}
        </ElButton>
      </template>

      <template #toolbar-utility>
        <ElButton
          class="hfl-refresh-button"
          :title="t('protection.retentionPage.btnRefresh')"
          :aria-label="t('protection.retentionPage.btnRefresh')"
          :disabled="loading"
          @click="load"
        >
          <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
        </ElButton>
      </template>

      <ElAlert
        v-if="listError"
        type="error"
        show-icon
        :closable="false"
        class="mb-3"
        :title="listError"
      >
        <template #default>
          <ElButton size="small" @click="load">
            {{ t('protection.retentionPage.btnRetry') }}
          </ElButton>
        </template>
      </ElAlert>

      <template #table="{ tableMaxHeight }">
        <el-table
          v-table-overflow-title
          v-loading="loading"
          :data="rows"
          :max-height="tableMaxHeight"
          class="hfl-list-table"
          stripe
          row-key="id"
        >
          <el-table-column
            prop="name"
            :label="t('protection.retentionPage.colRule')"
            min-width="180"
          />
          <el-table-column :label="t('protection.retentionPage.colStatus')" width="100">
            <template #default="{ row }">
              <el-tag
                :type="booleanStatusTag(row.is_active).type"
                :class="booleanStatusTag(row.is_active).class"
                size="small"
              >
                {{ row.is_active ? t('protection.retentionPage.statusOn') : t('protection.retentionPage.statusPaused') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.retentionPage.colSpec')" min-width="420">
            <template #default="{ row }">
              <div v-if="retentionSpecItems(row.spec).length" class="flex min-w-0 flex-wrap gap-x-4 gap-y-1">
                <span
                  v-for="item in retentionSpecItems(row.spec)"
                  :key="item.key"
                  class="min-w-0 text-sm text-[var(--el-text-color-regular)]"
                >
                  {{ t('protection.retentionPage.specValue', { label: item.label, value: item.value }) }}
                </span>
              </div>
              <span v-else class="hfl-empty-mark">{{ t('common.empty') }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="updated_at"
            :label="t('protection.retentionPage.colUpdated')"
            min-width="180"
          >
            <template #default="{ row }">
              <span class="hfl-table-cell-time">{{ formatDate(row.updated_at) }}</span>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="t('protection.retentionPage.empty')" :image-size="80" />
          </template>
        </el-table>
      </template>

      <template #footer>
        <HflPagination
          class="hfl-list-footer__pagination"
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
        />
      </template>
    </HflTablePanel>

    <Modal
      :open="open"
      :title="t('protection.retentionPage.modalTitle')"
      @close="open = false"
    >
      <ElForm label-position="right" label-width="auto" @submit.prevent="save">
        <ElFormItem
          :label="t('protection.retentionPage.labelOrgId')"
          :error="formErrors.organization"
          required
        >
          <ElInput
            v-model="form.organization"
            :placeholder="t('protection.retentionPage.phOrgId')"
            @input="formErrors.organization = ''"
          />
        </ElFormItem>
        <ElFormItem
          :label="t('protection.retentionPage.labelRuleName')"
          :error="formErrors.name"
          required
        >
          <ElInput
            v-model="form.name"
            :placeholder="t('protection.retentionPage.phRuleName')"
            @input="formErrors.name = ''"
          />
        </ElFormItem>
      </ElForm>
      <div class="mt-4 flex justify-end gap-2">
        <ElButton :disabled="saving" @click="open = false">
          {{ t('common.cancel') }}
        </ElButton>
        <ElButton type="primary" :loading="saving" @click="save">
          {{ t('protection.retentionPage.btnSave') }}
        </ElButton>
      </div>
    </Modal>
  </ModulePage>
</template>
