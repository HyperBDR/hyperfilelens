<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CloudCog,
  Download,
  FileJson,
  RefreshCw,
  RotateCcw,
  Search,
  Upload,
  X,
} from 'lucide-vue-next'
import JsonCodeEditor from '../../../components/JsonCodeEditor.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import ModulePage from '../../../components/ModulePage.vue'
import WizardSteps from '../../../components/WizardSteps.vue'
import { useResponsiveDrawerWidth } from '../../../composables/useResponsiveDrawerWidth'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import {
  applyProviderImport,
  cancelProviderValidationRun,
  confirmProviderReset,
  createProviderValidationRun,
  diffProviderImport,
  exportProviders,
  fetchPlatformStorageProviders,
  retryProviderValidationRun,
  reviewProviderImport,
  reviewProviderReset,
  type PlatformStorageProvidersResponse,
  type ProviderImportReview,
  type ProviderImportPreview,
  type ProviderResetReview,
  type ProviderValidationRun,
  type ProviderValidationStatus,
  type StorageProvider,
  type StorageProviderConfig,
  type StorageProviderRegion,
} from '../../../lib/storageProviderCatalogApi'
import PlatformOpsDetailSection from '../../components/PlatformOpsDetailSection.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import ProviderDiffDialog from './ProviderDiffDialog.vue'
import ProviderDiffDetails from './ProviderDiffDetails.vue'
import ProviderImportRegionReview from './ProviderImportRegionReview.vue'

const { t } = useI18n()
const sideNav = usePlatformOpsSideNav()
const { drawerSize } = useResponsiveDrawerWidth(2)
const loading = ref(false)
const loadError = ref('')
const response = ref<PlatformStorageProvidersResponse | null>(null)
const selectedProviderId = ref('')
const selectedProviders = ref<StorageProvider[]>([])
const providerDetailsOpen = ref(false)
const regionSearch = ref('')
const actionLoading = ref(false)
const validationRefreshLoading = ref(false)
const VALIDATION_REGION_LIMIT = 10
let pollTimer: number | null = null
let validationPollTimer: number | null = null

const providers = computed(() => response.value?.providers || [])
const selectedProvider = computed(() => (
  providers.value.find((provider) => provider.id === selectedProviderId.value) || null
))
const runByProvider = computed(() => Object.fromEntries(
  (response.value?.validation_runs || []).map((run) => [run.provider_id, run]),
))
const selectedRun = computed(() => selectedProvider.value ? runByProvider.value[selectedProvider.value.id] : undefined)
const filteredRegions = computed(() => {
  const query = regionSearch.value.trim().toLowerCase()
  const regions = selectedProvider.value?.regions || []
  if (!query) return regions
  return regions.filter((region) => [
    region.id,
    region.display_name,
    region.region_group,
    region.region_group_en,
    region.external_endpoint,
    region.internal_endpoint,
  ]
    .some((value) => value.toLowerCase().includes(query)))
})
const activeStatuses: ProviderValidationStatus[] = [
  'pending', 'validating', 'cancelling',
]
const hasActiveRun = computed(() => (response.value?.validation_runs || [])
  .some((run) => activeStatuses.includes(run.status)))

function statusLabel(status: string) {
  return t(`platformOps.storageProviders.status.${status}`)
}

function statusType(status: string) {
  if (['success', 'passed', 'passed_complete'].includes(status)) return 'success'
  if (status === 'passed_partial') return 'warning'
  if (['validation_failed', 'failed', 'cleanup_required'].includes(status)) return 'danger'
  if (['cancelled', 'expired', 'not_run', 'stale'].includes(status)) return 'info'
  return 'warning'
}

function providerSourceLabel(source: string) {
  return t(`platformOps.storageProviders.source.${source}`)
}

function openProviderDetails(provider: StorageProvider, column?: { type?: string }) {
  if (column?.type === 'selection') return
  selectedProviderId.value = provider.id
  regionSearch.value = ''
  providerDetailsOpen.value = true
}

function clearProviderDetails() {
  selectedProviderId.value = ''
  regionSearch.value = ''
}

async function load({ quiet = false } = {}) {
  if (!quiet) loading.value = true
  loadError.value = ''
  try {
    response.value = await fetchPlatformStorageProviders()
    for (const run of response.value.validation_runs) {
      if (importRuns[run.provider_id]) importRuns[run.provider_id] = run
    }
    if (providerDetailsOpen.value && !selectedProvider.value) providerDetailsOpen.value = false
  } catch (error) {
    loadError.value = apiErrorMessage(error, t('platformOps.storageProviders.loadFailed'))
  } finally {
    if (!quiet) loading.value = false
  }
}

// Import Edit -> Review -> Apply flow.
type ImportCredential = { access_key_id: string; secret_access_key: string }
const importOpen = ref(false)
const importStep = ref<'editing' | 'reviewing' | 'success'>('editing')
const importContent = ref('')
const importPreview = ref<ProviderImportPreview | null>(null)
const diffDialogOpen = ref(false)
const importReview = ref<ProviderImportReview | null>(null)
const importError = ref('')
const importCredentials = reactive<Record<string, ImportCredential>>({})
const importRegionIds = reactive<Record<string, string[]>>({})
const importRuns = reactive<Record<string, ProviderValidationRun>>({})
const validationLoading = reactive<Record<string, boolean>>({})
const validationDialogStep = ref<'scope' | 'result'>('scope')
const validationProviderId = ref('')
const validationDialogError = ref('')

const importWizardSteps = computed(() => [
  { step: 'editing', label: t('platformOps.storageProviders.editConfiguration'), icon: FileJson },
  { step: 'reviewing', label: t('platformOps.storageProviders.review'), icon: CloudCog },
  { step: 'success', label: t('platformOps.storageProviders.done'), icon: Check },
])

function clearSecrets() {
  for (const value of Object.values(importCredentials)) {
    value.access_key_id = ''
    value.secret_access_key = ''
  }
}

const parsedImportProviders = computed<StorageProviderConfig[]>(() => {
  try {
    const value = JSON.parse(importContent.value)
    return Array.isArray(value?.providers) ? value.providers : []
  } catch {
    return []
  }
})

const validationProvider = computed(() => (
  parsedImportProviders.value.find((provider) => provider.id === validationProviderId.value) || null
))
const selectedValidationRegionIds = computed(() => {
  const provider = validationProvider.value
  return provider ? importRegionIds[provider.id] || [] : []
})
const validationRegionGroups = computed(() => {
  const groups = new Map<string, { label: string; regions: StorageProviderRegion[] }>()
  for (const region of validationProvider.value?.regions || []) {
    const key = region.region_group || region.region_group_en || region.id
    const group = groups.get(key) || {
      label: region.region_group_en || region.region_group || key,
      regions: [],
    }
    group.regions.push(region)
    groups.set(key, group)
  }
  return Array.from(groups, ([key, group]) => ({ key, ...group }))
})
const validationRun = computed(() => (
  validationProvider.value ? importRun(validationProvider.value.id) : undefined
))
const canStartValidation = computed(() => {
  const provider = validationProvider.value
  if (!provider) return false
  const credentials = importCredentials[provider.id]
  const regionCount = importRegionIds[provider.id]?.length || 0
  return Boolean(
    credentials?.access_key_id
    && credentials.secret_access_key
    && regionCount >= 1
    && regionCount <= VALIDATION_REGION_LIMIT,
  )
})

async function refreshValidationTool() {
  if (validationRefreshLoading.value) return
  validationRefreshLoading.value = true
  try {
    await load({ quiet: true })
    const run = validationRun.value
    if (run && activeStatuses.includes(run.status)) validationDialogStep.value = 'result'
  } finally {
    validationRefreshLoading.value = false
  }
}

watch(() => hasActiveRun.value && !importOpen.value, (active) => {
  if (active && pollTimer === null) {
    pollTimer = window.setInterval(() => void load({ quiet: true }), 3000)
  } else if (!active && pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}, { immediate: true })

watch(() => importOpen.value && importStep.value === 'editing', (visible) => {
  if (visible && validationPollTimer === null) {
    void refreshValidationTool()
    validationPollTimer = window.setInterval(() => void refreshValidationTool(), 15_000)
  } else if (!visible && validationPollTimer !== null) {
    window.clearInterval(validationPollTimer)
    validationPollTimer = null
  }
}, { immediate: true })

onMounted(load)
onBeforeUnmount(() => {
  if (pollTimer !== null) window.clearInterval(pollTimer)
  if (validationPollTimer !== null) window.clearInterval(validationPollTimer)
  clearSecrets()
})

watch(parsedImportProviders, (items) => {
  for (const provider of items) {
    importCredentials[provider.id] ||= { access_key_id: '', secret_access_key: '' }
    const available = new Set(provider.regions.map((region) => region.id))
    importRegionIds[provider.id] = (importRegionIds[provider.id] || [])
      .filter((regionId) => available.has(regionId))
  }
  if (!items.some((provider) => provider.id === validationProviderId.value)) {
    clearSecrets()
    validationProviderId.value = items[0]?.id || ''
    validationDialogStep.value = validationProviderId.value && importRun(validationProviderId.value)
      ? 'result'
      : 'scope'
  }
}, { flush: 'sync' })

function importRun(providerId: string) {
  return importRuns[providerId] || runByProvider.value[providerId]
}

async function validateImportProvider(provider: StorageProviderConfig, showSuccess = true) {
  validationLoading[provider.id] = true
  try {
    const credentials = importCredentials[provider.id] || { access_key_id: '', secret_access_key: '' }
    const run = await createProviderValidationRun({
      provider_id: provider.id,
      region_ids: importRegionIds[provider.id] || [],
      access_key_id: credentials.access_key_id,
      secret_access_key: credentials.secret_access_key,
      candidate_config: provider,
    })
    importRuns[provider.id] = run
    credentials.access_key_id = ''
    credentials.secret_access_key = ''
    if (showSuccess) ElMessage.success(t('platformOps.storageProviders.validationQueued'))
    await load({ quiet: true })
    return run
  } finally {
    validationLoading[provider.id] = false
  }
}

async function cancelImportValidation(provider: StorageProviderConfig) {
  const run = importRun(provider.id)
  if (!run) return
  validationLoading[provider.id] = true
  try {
    importRuns[provider.id] = await cancelProviderValidationRun(run.id)
    ElMessage.success(t('platformOps.storageProviders.cancelQueued'))
    await load({ quiet: true })
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, t('platformOps.storageProviders.actionFailed')))
  } finally {
    validationLoading[provider.id] = false
  }
}

async function retryImportValidation(provider: StorageProviderConfig) {
  const run = importRun(provider.id)
  if (!run) return
  validationLoading[provider.id] = true
  try {
    const credentials = importCredentials[provider.id]
    importRuns[provider.id] = await retryProviderValidationRun(
      run.id,
      credentials?.access_key_id || '',
      credentials?.secret_access_key || '',
    )
    if (credentials) {
      credentials.access_key_id = ''
      credentials.secret_access_key = ''
    }
    ElMessage.success(t('platformOps.storageProviders.retryQueued'))
    await load({ quiet: true })
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, t('platformOps.storageProviders.actionFailed')))
  } finally {
    validationLoading[provider.id] = false
  }
}

async function startValidation() {
  const provider = validationProvider.value
  if (!provider) return
  const credentials = importCredentials[provider.id]
  if (!credentials?.access_key_id || !credentials.secret_access_key) {
    validationDialogError.value = t('platformOps.storageProviders.credentialsRequired')
    return
  }
  const count = importRegionIds[provider.id]?.length || 0
  if (count < 1 || count > VALIDATION_REGION_LIMIT) {
    validationDialogError.value = t('platformOps.storageProviders.noValidationCandidates', {
      limit: VALIDATION_REGION_LIMIT,
    })
    return
  }
  validationDialogError.value = ''
  if (validationRun.value && activeStatuses.includes(validationRun.value.status)) {
    validationDialogStep.value = 'result'
    return
  }
  try {
    await validateImportProvider(provider)
    validationDialogStep.value = 'result'
  } catch (error) {
    validationDialogError.value = apiErrorMessage(error, t('platformOps.storageProviders.actionFailed'))
  }
}

function selectValidationProvider(providerId: string) {
  clearSecrets()
  validationProviderId.value = providerId
  validationDialogError.value = ''
  validationDialogStep.value = 'scope'
}

function selectValidationRegions(regionIds: string[]) {
  const provider = validationProvider.value
  if (!provider) return
  importRegionIds[provider.id] = regionIds
  validationDialogError.value = ''
}

async function submitValidationRetry() {
  const provider = validationProvider.value
  if (!provider) return
  const credentials = importCredentials[provider.id]
  if (!credentials?.access_key_id || !credentials.secret_access_key) {
    validationDialogError.value = t('platformOps.storageProviders.credentialsRequired')
    return
  }
  validationDialogError.value = ''
  await retryImportValidation(provider)
}

function beginNewValidation() {
  validationDialogError.value = ''
  validationDialogStep.value = 'scope'
}

function validationStepLabel(step: string | null) {
  return step ? t(`platformOps.storageProviders.status.${step}`) : '—'
}

function resetImportReview() {
  diffDialogOpen.value = false
  importPreview.value = null
  importReview.value = null
  if (importStep.value !== 'success') importStep.value = 'editing'
}

function setImportContent(value: string) {
  importContent.value = value
  importError.value = ''
  resetImportReview()
}

function openImport() {
  importStep.value = 'editing'
  importContent.value = JSON.stringify({ schema_version: 1, providers: [] }, null, 2)
  importError.value = ''
  importPreview.value = null
  diffDialogOpen.value = false
  importReview.value = null
  importOpen.value = true
}

function closeImport() {
  diffDialogOpen.value = false
  importOpen.value = false
  clearSecrets()
}

function formatImport() {
  try {
    setImportContent(JSON.stringify(JSON.parse(importContent.value), null, 2))
  } catch (error) {
    importError.value = jsonErrorWithLocation(error)
  }
}

function jsonErrorWithLocation(error: unknown) {
  const message = error instanceof Error ? error.message : String(error)
  const match = message.match(/position\s+(\d+)/i)
  if (!match) return message
  const position = Number(match[1])
  const line = importContent.value.slice(0, position).split('\n').length
  return t('platformOps.storageProviders.jsonLineError', { line, message })
}

async function uploadImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    importError.value = t('platformOps.storageProviders.fileTooLarge')
    return
  }
  setImportContent(await file.text())
}

async function previewImport() {
  actionLoading.value = true
  try {
    importPreview.value = await diffProviderImport(importContent.value)
    importError.value = ''
    diffDialogOpen.value = true
  } catch (error) {
    importError.value = apiErrorMessage(error, t('platformOps.storageProviders.invalidJson'))
  } finally {
    actionLoading.value = false
  }
}

async function nextImport() {
  actionLoading.value = true
  try {
    importReview.value = await reviewProviderImport(importContent.value)
    importStep.value = 'reviewing'
    importError.value = ''
  } catch (error) {
    importError.value = apiErrorMessage(error, t('platformOps.storageProviders.invalidJson'))
  } finally {
    actionLoading.value = false
  }
}

async function applyImport() {
  if (!importReview.value) return
  actionLoading.value = true
  try {
    await applyProviderImport(
      importContent.value,
      importReview.value,
      importReview.value.required_risk_confirmation_ids,
    )
    ElMessage.success(t('platformOps.storageProviders.applySuccess'))
    closeImport()
    await load()
  } catch (error) {
    importError.value = apiErrorMessage(error, t('platformOps.storageProviders.actionFailed'))
  } finally {
    actionLoading.value = false
  }
}

// Export and reset confirmation flows.
const resetOpen = ref(false)
const resetReview = ref<ProviderResetReview | null>(null)
const resetProviderId = ref<string | undefined>()

async function downloadProviders(providerIds?: string[]) {
  actionLoading.value = true
  try {
    const catalog = await exportProviders(providerIds)
    const blob = new Blob([`${JSON.stringify(catalog, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'storage-provider-catalog.json'
    anchor.click()
    URL.revokeObjectURL(url)
    ElMessage.success(t('platformOps.storageProviders.exportSuccess'))
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, t('platformOps.storageProviders.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function openReset(providerId?: string) {
  actionLoading.value = true
  try {
    resetReview.value = await reviewProviderReset(providerId)
    resetProviderId.value = providerId
    resetOpen.value = true
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, t('platformOps.storageProviders.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

async function confirmReset() {
  if (!resetReview.value) return
  actionLoading.value = true
  try {
    await confirmProviderReset(resetReview.value, resetProviderId.value)
    resetOpen.value = false
    ElMessage.success(t('platformOps.storageProviders.resetSuccess'))
    await load()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, t('platformOps.storageProviders.actionFailed')))
  } finally {
    actionLoading.value = false
  }
}

</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="storage-providers-page">
      <header class="storage-providers-page__header">
        <div>
          <p>{{ t('platformOps.storageProviders.subtitle') }}</p>
        </div>
        <div class="storage-providers-page__actions">
          <el-button :loading="loading" @click="load()"><RefreshCw :size="15" />{{ t('common.refresh') }}</el-button>
          <el-button :disabled="actionLoading" @click="openImport"><Upload :size="15" />{{ t('platformOps.storageProviders.import') }}</el-button>
          <el-dropdown>
            <el-button :disabled="actionLoading"><Download :size="15" />{{ t('platformOps.storageProviders.export') }}</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :disabled="selectedProviders.length === 0" @click="downloadProviders(selectedProviders.map((row) => row.id))">
                  {{ t('platformOps.storageProviders.exportSelected') }}
                </el-dropdown-item>
                <el-dropdown-item @click="downloadProviders()">{{ t('platformOps.storageProviders.exportAll') }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button type="danger" plain :disabled="actionLoading" @click="openReset()"><RotateCcw :size="15" />{{ t('platformOps.storageProviders.resetAll') }}</el-button>
        </div>
      </header>

      <el-alert v-if="loadError" type="error" :title="loadError" show-icon :closable="false">
        <template #default><el-button size="small" @click="load()">{{ t('common.retry') }}</el-button></template>
      </el-alert>

      <HflTablePanel fill>
        <template #table="{ tableMaxHeight }">
          <el-table
            v-loading="loading"
            :data="providers"
            row-key="id"
            stripe
            flexible
            class="hfl-list-table platform-ops-list-table--clickable"
            :max-height="tableMaxHeight"
            @selection-change="selectedProviders = $event"
            @row-click="openProviderDetails"
          >
            <el-table-column type="selection" width="42" />
            <el-table-column :label="t('platformOps.storageProviders.provider')" min-width="340">
              <template #default="{ row }">
                <button type="button" class="storage-providers-page__title-button" @click.stop="openProviderDetails(row)">{{ row.display_name }}</button>
                <small>{{ row.id }}</small>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.storageProviders.sourceLabel')" min-width="160">
              <template #default="{ row }"><el-tag size="small" effect="plain">{{ providerSourceLabel(row.source) }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="region_count" :label="t('platformOps.storageProviders.regions')" min-width="110" />
            <el-table-column :label="t('platformOps.storageProviders.updated')" min-width="170">
              <template #default="{ row }">
                <span class="hfl-table-cell-time">{{ formatLocalDateTime(row.updated_at, '—') }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.storageProviders.actions')" width="100" fixed="right" align="center">
              <template #default="{ row }">
                <div class="storage-providers-page__row-actions" @click.stop>
                  <button
                    type="button"
                    class="storage-providers-page__action-button"
                    :title="t('platformOps.storageProviders.reset')"
                    :disabled="row.source !== 'override'"
                    @click="openReset(row.id)"
                  >
                    <RotateCcw :size="14" class="storage-providers-page__action-icon" aria-hidden="true" />
                    <span>{{ t('platformOps.storageProviders.reset') }}</span>
                  </button>
                </div>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty :description="t('platformOps.storageProviders.empty')" :image-size="72" />
            </template>
          </el-table>
        </template>
      </HflTablePanel>
    </div>

    <el-drawer
      v-model="providerDetailsOpen"
      :size="drawerSize"
      class="hfl-detail-drawer storage-provider-drawer"
      destroy-on-close
      @closed="clearProviderDetails"
    >
      <template #header>
        <div v-if="selectedProvider" class="storage-provider-drawer__header">
          <div class="storage-provider-drawer__identity">
            <CloudCog :size="20" />
            <div>
              <h2>{{ selectedProvider.display_name }}</h2>
              <p>{{ selectedProvider.id }}</p>
            </div>
          </div>
          <el-tag :type="selectedProvider.enabled ? 'success' : 'info'">{{ selectedProvider.enabled ? t('platformOps.storageProviders.enabled') : t('platformOps.storageProviders.disabled') }}</el-tag>
        </div>
      </template>
      <div v-if="selectedProvider" class="hfl-detail-sections storage-provider-drawer__sections">
        <PlatformOpsDetailSection :title="t('platformOps.storageProviders.providerInfo')">
          <div class="hfl-detail-grid">
            <div class="hfl-detail-row">
              <span class="hfl-detail-row__label">{{ t('platformOps.storageProviders.providerId') }}</span>
              <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ selectedProvider.id }}</span>
            </div>
            <div class="hfl-detail-row">
              <span class="hfl-detail-row__label">{{ t('platformOps.storageProviders.sourceLabel') }}</span>
              <span class="hfl-detail-row__value"><el-tag size="small" effect="plain">{{ providerSourceLabel(selectedProvider.source) }}</el-tag></span>
            </div>
            <div class="hfl-detail-row">
              <span class="hfl-detail-row__label">{{ t('platformOps.storageProviders.updated') }}</span>
              <span class="hfl-detail-row__value hfl-table-cell-time">{{ formatLocalDateTime(selectedProvider.updated_at, '—') }}</span>
            </div>
            <div class="hfl-detail-row">
              <span class="hfl-detail-row__label">{{ t('platformOps.storageProviders.regions') }}</span>
              <span class="hfl-detail-row__value">{{ selectedProvider.region_count }}</span>
            </div>
            <div class="hfl-detail-row">
              <span class="hfl-detail-row__label">{{ t('platformOps.storageProviders.checksum') }}</span>
              <span class="hfl-detail-row__value hfl-detail-row__value--mono storage-provider-drawer__checksum" :title="selectedProvider.checksum">{{ selectedProvider.checksum }}</span>
            </div>
          </div>
        </PlatformOpsDetailSection>

        <PlatformOpsDetailSection v-if="selectedRun" :title="t('platformOps.storageProviders.validationRun')">
          <div class="storage-provider-drawer__run-summary">
            <el-tag :type="statusType(selectedRun.status)">{{ statusLabel(selectedRun.status) }}</el-tag>
            <span>{{ t('platformOps.storageProviders.progress', { completed: selectedRun.completed_region_count, total: selectedRun.region_count, failed: selectedRun.failed_region_count }) }}</span>
            <router-link v-if="selectedRun.task_uuid" :to="{ path: '/platform-ops/monitoring/tasks', query: { search: selectedRun.task_uuid } }">{{ t('platformOps.storageProviders.viewTask') }}</router-link>
          </div>
        </PlatformOpsDetailSection>

        <PlatformOpsDetailSection :title="t('platformOps.storageProviders.regions')">
          <div class="storage-provider-drawer__region-search">
            <el-input v-model="regionSearch" clearable :placeholder="t('platformOps.storageProviders.searchRegions')"><template #prefix><Search :size="14" /></template></el-input>
          </div>
          <el-table
            :data="filteredRegions"
            stripe
            max-height="var(--storage-provider-regions-table-max-height)"
            scrollbar-always-on
            class="storage-provider-drawer__regions-table"
            empty-text="—"
          >
            <el-table-column :label="t('platformOps.storageProviders.region')" min-width="220">
              <template #default="{ row }"><strong>{{ row.display_name }}</strong><small>{{ row.id }} · {{ row.region_group_en }}</small></template>
            </el-table-column>
            <el-table-column :label="t('platformOps.storageProviders.externalEndpoint')" min-width="280" show-overflow-tooltip>
              <template #default="{ row }"><span class="storage-provider-drawer__endpoint">{{ row.external_endpoint }}</span></template>
            </el-table-column>
            <el-table-column :label="t('platformOps.storageProviders.internalEndpoint')" min-width="280" show-overflow-tooltip>
              <template #default="{ row }"><span class="storage-provider-drawer__endpoint">{{ row.internal_endpoint }}</span></template>
            </el-table-column>
          </el-table>
        </PlatformOpsDetailSection>
      </div>
    </el-drawer>

    <Teleport to="body">
      <div v-if="importOpen" class="fullscreen-form-fullscreen fullscreen-form-animated provider-import-fullscreen">
        <div class="fullscreen-form-page provider-import-page">
          <header class="fullscreen-form-header">
            <button type="button" class="fullscreen-form-header__back" @click="closeImport">
              <ArrowLeft class="fullscreen-form-header__back-icon" :size="18" />
            </button>
            <div class="fullscreen-form-header__content">
              <h1 class="fullscreen-form-header__title">{{ t('platformOps.storageProviders.importTitle') }}</h1>
              <p class="fullscreen-form-header__desc">{{ t('platformOps.storageProviders.importDescription') }}</p>
            </div>
          </header>
          <div class="fullscreen-form-layout provider-import-layout">
            <WizardSteps
              as="aside"
              class="provider-import-steps"
              :steps="importWizardSteps"
              :current-step="importStep"
              :is-done="(_, index) => index < (importStep === 'editing' ? 0 : importStep === 'reviewing' ? 1 : 2)"
              :clickable="false"
              :aria-label="t('platformOps.storageProviders.importTitle')"
            />
            <main class="fullscreen-form-main provider-import-main">
              <div class="provider-import-workspace" :class="{ 'provider-import-workspace--with-tool': importStep === 'editing' }">
                <div class="provider-import-content" :class="{ 'provider-import-content--editing': importStep === 'editing' }">
                <template v-if="importStep === 'editing'">
                  <div class="storage-providers-page__editor-toolbar">
                    <label class="el-button"><FileJson :size="15" />{{ t('platformOps.storageProviders.uploadJson') }}<input type="file" accept="application/json,.json" hidden @change="uploadImport" /></label>
                    <el-button @click="formatImport">{{ t('platformOps.storageProviders.formatJson') }}</el-button>
                  </div>
                  <JsonCodeEditor :model-value="importContent" :aria-label="t('platformOps.storageProviders.catalogEditor')" @update:model-value="setImportContent" />
                  <el-alert v-if="importError" type="error" :title="importError" show-icon :closable="false" />
                </template>
                <template v-else-if="importStep === 'reviewing' && importReview">
                  <ProviderImportRegionReview :providers="parsedImportProviders" />
                  <el-alert v-if="importError" type="error" :title="importError" show-icon :closable="false" />
                </template>
                <el-result v-else icon="success" :title="t('platformOps.storageProviders.applySuccess')" :sub-title="t('platformOps.storageProviders.applySuccessHint')" />
                </div>

                <aside v-if="importStep === 'editing'" class="provider-validation-tool" :aria-label="t('platformOps.storageProviders.validationDialogTitle')">
                  <header class="provider-validation-tool__header">
                    <div>
                      <h2>{{ t('platformOps.storageProviders.validationDialogTitle') }}</h2>
                    </div>
                    <div class="provider-validation-tool__header-actions">
                      <el-tag v-if="validationRun" size="small" :type="statusType(validationRun.status)">{{ statusLabel(validationRun.status) }}</el-tag>
                      <button
                        class="provider-validation-tool__refresh"
                        type="button"
                        :title="t('common.refresh')"
                        :aria-label="t('common.refresh')"
                        :disabled="validationRefreshLoading"
                        @click="refreshValidationTool"
                      >
                        <RefreshCw
                          class="provider-validation-tool__refresh-icon"
                          :class="{ 'provider-validation-tool__refresh-icon--spinning': validationRefreshLoading }"
                          :size="16"
                        />
                      </button>
                    </div>
                  </header>
                  <el-alert type="warning" :title="t('platformOps.storageProviders.costWarning')" show-icon :closable="false" />

                  <div v-if="!parsedImportProviders.length" class="provider-validation-tool__empty">
                    <el-empty :description="t('platformOps.storageProviders.noProvidersToValidate')" :image-size="64" />
                  </div>
                  <template v-else-if="validationDialogStep === 'scope'">
                    <div class="provider-validation-tool__body">
                      <el-form label-position="top">
                        <el-form-item :label="t('platformOps.storageProviders.validationProvider')">
                          <el-select :model-value="validationProviderId" :teleported="false" @update:model-value="selectValidationProvider">
                            <el-option v-for="provider in parsedImportProviders" :key="provider.id" :label="provider.display_name || provider.id" :value="provider.id" />
                          </el-select>
                        </el-form-item>
                        <el-form-item v-if="validationProvider" :label="t('platformOps.storageProviders.accessKeyId')">
                          <el-input v-model="importCredentials[validationProvider.id].access_key_id" autocomplete="off" />
                        </el-form-item>
                        <el-form-item v-if="validationProvider" :label="t('platformOps.storageProviders.secretAccessKey')">
                          <el-input v-model="importCredentials[validationProvider.id].secret_access_key" type="password" autocomplete="new-password" show-password />
                        </el-form-item>
                        <el-form-item :label="t('platformOps.storageProviders.selectValidationRegions')">
                          <el-select
                            v-if="validationProvider"
                            class="provider-validation-tool__region-select"
                            :model-value="selectedValidationRegionIds"
                            multiple
                            filterable
                            clearable
                            :multiple-limit="VALIDATION_REGION_LIMIT"
                            :teleported="false"
                            :placeholder="t('platformOps.storageProviders.selectValidationRegions')"
                            @update:model-value="selectValidationRegions"
                          >
                            <template #tag>
                              <span
                                v-if="selectedValidationRegionIds.length"
                                class="provider-validation-tool__region-selection-summary"
                              >
                                <Check :size="13" aria-hidden="true" />
                                {{ t('platformOps.storageProviders.validationRegionsSelected', { count: selectedValidationRegionIds.length, limit: VALIDATION_REGION_LIMIT }) }}
                              </span>
                            </template>
                            <el-option-group
                              v-for="group in validationRegionGroups"
                              :key="group.key"
                              :label="group.label"
                            >
                              <el-option
                                v-for="region in group.regions"
                                :key="region.id"
                                :label="`${region.display_name} (${region.id})`"
                                :value="region.id"
                              >
                                <div
                                  class="provider-validation-tool__region-option"
                                  :title="`${region.display_name} (${region.id})`"
                                >
                                  <strong>{{ region.display_name || region.id }}</strong>
                                  <code>{{ region.id }}</code>
                                </div>
                              </el-option>
                            </el-option-group>
                          </el-select>
                          <small>{{ t('platformOps.storageProviders.selectedRegionLimit', { limit: VALIDATION_REGION_LIMIT }) }}</small>
                        </el-form-item>
                      </el-form>
                      <small class="provider-validation-tool__security-note">{{ t('platformOps.storageProviders.credentialSecurityNote') }}</small>
                    </div>
                    <div class="provider-validation-tool__actions"><el-button type="primary" :disabled="!canStartValidation" :loading="validationProvider ? validationLoading[validationProvider.id] : false" @click="startValidation">{{ t('platformOps.storageProviders.startValidation') }}</el-button></div>
                  </template>
                  <template v-else-if="validationDialogStep === 'result' && validationProvider">
                    <div class="provider-validation-tool__body">
                      <div v-if="validationRun" class="provider-validation-tool__summary"><strong>{{ validationProvider.display_name || validationProvider.id }}</strong><span>{{ t('platformOps.storageProviders.progress', { completed: validationRun.completed_region_count, total: validationRun.region_count, failed: validationRun.failed_region_count }) }}</span></div>
                      <el-empty v-else :description="t('platformOps.storageProviders.noValidationRun')" :image-size="64" />
                      <div v-if="validationRun" class="provider-validation-tool__results">
                        <div v-for="row in validationRun.regions" :key="row.id">
                          <div><strong>{{ row.region_id }}</strong><span>{{ validationStepLabel(row.current_step) }}</span></div>
                          <el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
                          <p v-if="row.error_message" :title="row.error_message">{{ row.error_message }}</p>
                        </div>
                      </div>
                      <section v-if="validationRun && ['validation_failed', 'cleanup_required'].includes(validationRun.status)" class="provider-validation-tool__retry">
                        <h3>{{ t('platformOps.storageProviders.retryValidation') }}</h3>
                        <el-form label-position="top">
                          <el-form-item :label="t('platformOps.storageProviders.accessKeyId')"><el-input v-model="importCredentials[validationProvider.id].access_key_id" autocomplete="off" /></el-form-item>
                          <el-form-item :label="t('platformOps.storageProviders.secretAccessKey')"><el-input v-model="importCredentials[validationProvider.id].secret_access_key" type="password" autocomplete="new-password" show-password /></el-form-item>
                        </el-form>
                      </section>
                    </div>
                    <div class="provider-validation-tool__actions">
                      <el-button v-if="validationRun && activeStatuses.includes(validationRun.status)" type="danger" plain :loading="validationLoading[validationProvider.id]" @click="cancelImportValidation(validationProvider)">{{ t('common.stop') }}</el-button>
                      <template v-else-if="validationRun?.status === 'validation_failed'">
                        <el-button type="warning" :disabled="!importCredentials[validationProvider.id]?.access_key_id || !importCredentials[validationProvider.id]?.secret_access_key" :loading="validationLoading[validationProvider.id]" @click="submitValidationRetry">{{ t('platformOps.storageProviders.retryValidation') }}</el-button>
                        <el-button type="primary" @click="beginNewValidation">{{ t('platformOps.storageProviders.newValidation') }}</el-button>
                      </template>
                      <el-button v-else-if="validationRun?.status === 'cleanup_required'" type="warning" :disabled="!importCredentials[validationProvider.id]?.access_key_id || !importCredentials[validationProvider.id]?.secret_access_key" :loading="validationLoading[validationProvider.id]" @click="submitValidationRetry">{{ t('platformOps.storageProviders.retryValidation') }}</el-button>
                      <el-button v-else type="primary" @click="beginNewValidation">{{ t('platformOps.storageProviders.newValidation') }}</el-button>
                    </div>
                  </template>
                  <el-alert v-if="validationDialogError" class="provider-validation-tool__error" type="error" :title="validationDialogError" show-icon :closable="false" />
                </aside>
              </div>
            </main>
          </div>
          <footer class="fullscreen-form-footer provider-import-footer">
            <div class="provider-import-footer__actions">
              <el-button class="hfl-btn-with-icon" @click="closeImport"><X :size="14" /><span>{{ importStep === 'success' ? t('common.close') : t('common.cancel') }}</span></el-button>
              <template v-if="importStep === 'editing'">
                <el-button :loading="actionLoading" @click="previewImport">{{ t('platformOps.storageProviders.diff') }}</el-button>
                <el-button type="primary" class="hfl-btn-with-icon" :loading="actionLoading" @click="nextImport"><span>{{ t('common.next') }}</span><ArrowRight :size="14" /></el-button>
              </template>
              <template v-else-if="importStep === 'reviewing'">
                <el-button class="hfl-btn-with-icon" @click="importStep = 'editing'"><ArrowLeft :size="14" /><span>{{ t('common.back') }}</span></el-button>
                <el-button type="primary" class="hfl-btn-with-icon" :loading="actionLoading" @click="applyImport"><Check :size="14" /><span>{{ t('platformOps.storageProviders.apply') }}</span></el-button>
              </template>
            </div>
          </footer>
        </div>
      </div>
    </Teleport>

    <ProviderDiffDialog v-model="diffDialogOpen" :preview="importPreview" />

    <el-dialog
      v-model="resetOpen"
      class="provider-reset-dialog"
      :title="t('platformOps.storageProviders.resetTitle')"
      width="min(720px, 92vw)"
      top="6vh"
      append-to-body
      destroy-on-close
    >
      <div class="provider-reset-dialog__content">
        <el-alert type="warning" :title="t('platformOps.storageProviders.resetWarning')" show-icon :closable="false" />
        <ProviderDiffDetails v-if="resetReview" :diffs="resetReview.providers" />
      </div>
      <template #footer><el-button @click="resetOpen = false">{{ t('common.cancel') }}</el-button><el-button type="danger" :loading="actionLoading" @click="confirmReset">{{ t('platformOps.storageProviders.confirmReset') }}</el-button></template>
    </el-dialog>
  </ModulePage>
</template>

<style src="../../../styles/fullscreen-form-shell.css"></style>

<style scoped>
.storage-providers-page { display: flex; min-height: 0; flex: 1; flex-direction: column; gap: 14px; padding: 18px; overflow: hidden; }
.storage-providers-page__header, .storage-providers-page__actions, .storage-providers-page__run-head, .storage-providers-page__editor-toolbar { display: flex; align-items: center; gap: 10px; }
.storage-providers-page__header { justify-content: space-between; }
.storage-providers-page__header p { margin: 0; color: var(--color-text-secondary, #70707e); font-size: 13px; }
.storage-providers-page__actions { flex-wrap: wrap; justify-content: flex-end; }
.storage-providers-page__actions :deep(.el-button span), .storage-providers-page__editor-toolbar .el-button { gap: 6px; }
.storage-providers-page :deep(.hfl-list-panel) { flex: 1 1 auto; min-height: 0; }
.storage-providers-page small, .storage-provider-drawer small { display: block; margin-top: 3px; color: var(--color-text-secondary, #777786); font-size: 11px; }
.storage-providers-page__title-button { display: block; max-width: 100%; padding: 0; overflow: hidden; border: 0; background: transparent; color: var(--color-primary, #6d5ef6); cursor: pointer; font: inherit; font-weight: 600; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.storage-providers-page__title-button:hover, .storage-providers-page__title-button:focus-visible { color: var(--el-color-primary-dark-2, #5548d9); outline: none; text-decoration: underline; text-underline-offset: 3px; }
.storage-providers-page__row-actions { display: flex; width: 100%; align-items: center; justify-content: center; white-space: nowrap; }
.storage-providers-page__action-button { appearance: button; display: inline-flex; box-sizing: border-box; align-items: center; justify-content: center; gap: 6px; margin: 0; padding: 4px 10px; border: 1px solid oklch(87% 0.065 274.039); border-radius: 6px; background: #fff; color: oklch(51.1% 0.262 276.966); cursor: pointer; font-family: inherit; font-size: 12px; font-weight: 500; letter-spacing: normal; line-height: 16px; white-space: nowrap; box-shadow: 0 1px 2px 0 rgb(0 0 0 / 5%); transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1); }
.storage-providers-page__action-icon { width: 14px; height: 14px; flex: 0 0 14px; color: oklch(58.5% 0.233 277.117); }
.storage-providers-page__action-button:not(:disabled):hover { border-color: oklch(78.5% 0.115 274.713); background: oklch(96.2% 0.018 272.314); }
.storage-providers-page__action-button:disabled { border-color: oklch(92.9% 0.013 255.508); background: oklch(98.4% 0.003 247.858); color: oklch(70.4% 0.04 256.788); opacity: .7; box-shadow: none; cursor: not-allowed; }
.storage-providers-page__action-button:disabled .storage-providers-page__action-icon { color: oklch(70.4% 0.04 256.788); }
.storage-providers-page__action-button:focus-visible { outline: 2px solid rgba(99, 102, 241, .28); outline-offset: 2px; }
.storage-provider-drawer__header, .storage-provider-drawer__identity, .storage-provider-drawer__run-summary { display: flex; align-items: center; gap: 10px; }
.storage-provider-drawer__header { width: 100%; min-width: 0; justify-content: space-between; }
.storage-provider-drawer__identity { min-width: 0; }
.storage-provider-drawer__identity > div { min-width: 0; }
.storage-provider-drawer__identity h2 { margin: 0; overflow: hidden; color: var(--color-text-title, #1c1c26); font-size: 18px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.storage-provider-drawer__identity p { margin: 4px 0 0; color: var(--color-text-secondary, #70707e); font: 12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.storage-provider-drawer__sections { --storage-provider-regions-table-max-height: clamp(280px, calc(100dvh - 470px), 560px); padding-bottom: 8px; }
.storage-provider-drawer__sections :deep(.hfl-detail-section__title) { display: flex; align-items: center; gap: 8px; }
.storage-provider-drawer__sections :deep(.hfl-detail-section__title::before) { width: 3px; height: 16px; flex: 0 0 auto; border-radius: 999px; background: var(--color-primary, #6d5ef6); content: ''; }
.storage-provider-drawer__checksum { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.storage-provider-drawer__run-summary { flex-wrap: wrap; padding: 16px; font-size: 12px; }
.storage-provider-drawer__run-summary a { margin-left: auto; color: var(--color-primary, #6d5ef6); }
.storage-provider-drawer__region-search { padding: 14px 16px; border-bottom: 1px solid var(--el-border-color-lighter); }
.storage-provider-drawer__regions-table { width: 100%; }
.storage-provider-drawer__endpoint { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
.storage-providers-page__credentials { display: grid; grid-template-columns: 1fr 1fr auto; gap: 10px; margin: 14px 0; }
.storage-providers-page__run-head { margin: 14px 0; color: var(--color-text-secondary, #777786); font-size: 12px; }
.storage-providers-page__region-status { max-height: 220px; margin-top: 12px; overflow: auto; border: 1px solid var(--color-border-light, #ededf3); border-radius: 8px; }
.storage-providers-page__region-status > div { display: grid; grid-template-columns: minmax(130px, 1fr) auto minmax(120px, .7fr) minmax(180px, 1fr); align-items: center; gap: 8px; padding: 8px 10px; border-bottom: 1px solid var(--color-border-light, #ededf3); font-size: 12px; }
.storage-providers-page__editor-toolbar { margin: 14px 0 8px; }
.storage-providers-page__editor-toolbar label { display: inline-flex; align-items: center; gap: 6px; }
.provider-reset-dialog__content { min-height: 0; }
:global(.provider-reset-dialog) { display: flex; max-height: 88dvh; flex-direction: column; margin-bottom: 0; }
:global(.provider-reset-dialog .el-dialog__header), :global(.provider-reset-dialog .el-dialog__footer) { flex: 0 0 auto; }
:global(.provider-reset-dialog .el-dialog__body) { min-height: 0; flex: 1 1 auto; overflow-y: auto; }
.provider-reset-dialog__content :deep(.provider-diff) { margin-top: 12px; }
.provider-import-fullscreen { position: fixed; inset: var(--topnav-height, var(--app-header-height, 52px)) 0 0; z-index: 3000; overflow: hidden; background: #f2f3f5; color: #1d2129; }
.provider-import-page { box-sizing: border-box; display: flex; flex-direction: column; width: 100%; height: 100%; min-height: 0; padding: 28px 28px calc(88px + var(--app-safe-bottom)); overflow: hidden; }
.provider-import-page :deep(.fullscreen-form-header) { flex: 0 0 auto; width: min(100%, 1600px); margin: 0 auto 16px; }
.provider-import-layout { display: flex; flex: 1 1 auto; flex-direction: column; gap: 24px; width: min(100%, 1600px); min-height: 0; margin: 0 auto; }
.provider-import-steps { align-self: flex-start; }
.provider-import-main { flex: 1 1 auto; min-width: 0; min-height: 0; overflow: hidden; border: 1px solid color-mix(in srgb, var(--color-primary, #6d5ef6) 55%, transparent); border-radius: 8px; background: #fff; box-shadow: inset 3px 0 0 color-mix(in srgb, var(--color-primary, #6d5ef6) 85%, transparent), 0 8px 20px rgba(15, 23, 42, .04); }
.provider-import-workspace { display: grid; width: 100%; height: 100%; min-height: 0; }
.provider-import-workspace--with-tool { grid-template-columns: minmax(0, 1fr) 368px; }
.provider-import-content { display: flex; min-width: 0; min-height: 100%; flex-direction: column; gap: 14px; padding: 24px; overflow: auto; }
.provider-import-content--editing :deep(.hfl-json-editor) { min-height: 360px; flex: 1 1 auto; }
.provider-import-content--editing :deep(.hfl-json-editor .cm-editor) { height: 100%; min-height: 360px; }
.provider-validation-tool { display: flex; min-width: 0; min-height: 0; flex-direction: column; gap: 14px; padding: 20px; overflow: auto; border-left: 1px solid var(--color-border-light, #e6e7ee); background: var(--color-fill-light, #fafafe); }
.provider-validation-tool__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.provider-validation-tool__header h2 { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--color-text-title, #1c1c26); font-size: 15px; font-weight: 650; }
.provider-validation-tool__header h2::before { width: 3px; height: 16px; flex: 0 0 auto; border-radius: 999px; background: var(--color-primary, #6d5ef6); content: ''; }
.provider-validation-tool__header-actions { display: flex; flex: 0 0 auto; align-items: center; justify-content: flex-end; gap: 7px; }
.provider-validation-tool__refresh { display: inline-flex; width: 40px; height: 34px; flex: 0 0 40px; align-items: center; justify-content: center; padding: 0; border: 1px solid #c8d3e0; border-radius: 6px; background: #f8fbff; color: #64748b; cursor: pointer; transition: all .15s ease; }
.provider-validation-tool__refresh:hover:not(:disabled) { border-color: #7a99bc; background: #f1f6fc; color: var(--color-primary, #457ab0); }
.provider-validation-tool__refresh:focus-visible { outline: 2px solid color-mix(in srgb, var(--color-primary, #457ab0) 30%, transparent); outline-offset: 2px; }
.provider-validation-tool__refresh:disabled { opacity: .6; cursor: not-allowed; }
.provider-validation-tool__refresh-icon { flex-shrink: 0; }
.provider-validation-tool__refresh-icon--spinning { animation: provider-validation-refresh-spin .8s linear infinite; }
@keyframes provider-validation-refresh-spin { to { transform: rotate(360deg); } }
:root[data-theme="dark"] .provider-validation-tool__refresh { border-color: #3b4658; background: #1b202a; color: var(--color-text-secondary, #a3a6ad); }
:root[data-theme="dark"] .provider-validation-tool__refresh:hover:not(:disabled) { border-color: #5a6f8f; background: #202736; color: #fff; }
.provider-validation-tool__body { display: grid; gap: 14px; }
.provider-validation-tool__body :deep(.el-select), .provider-validation-tool__body :deep(.el-input) { width: 100%; }
.provider-validation-tool__body :deep(.el-form-item) { margin-bottom: 14px; }
.provider-validation-tool__body small { display: block; margin-top: 5px; color: var(--color-text-secondary, #777786); font-size: 11px; }
.provider-validation-tool__region-select :deep(.el-select__wrapper) { min-height: 40px; padding: 6px 10px; border-radius: 6px; }
.provider-validation-tool__region-select :deep(.el-select__selection.is-near) { margin-left: 0; }
.provider-validation-tool__region-selection-summary { display: inline-flex; min-width: 0; max-width: 100%; align-items: center; gap: 5px; padding: 1px 8px; overflow: hidden; border-radius: 5px; background: var(--el-color-primary-light-9, #eef2ff); color: var(--color-primary, #6d5ef6); font-size: 12px; font-weight: 600; line-height: 22px; text-overflow: ellipsis; white-space: nowrap; }
.provider-validation-tool__region-selection-summary svg { flex: 0 0 auto; }
.provider-validation-tool__region-select :deep(.el-select-group__title) { height: 30px; padding: 7px 16px 3px; color: var(--color-text-secondary, #777786); font-size: 11px; font-weight: 650; line-height: 20px; }
.provider-validation-tool__region-select :deep(.el-select-dropdown__item) { display: flex; height: auto; min-height: 48px; align-items: center; padding: 7px 38px 7px 16px; line-height: normal; }
.provider-validation-tool__region-option { display: grid; min-width: 0; width: 100%; gap: 3px; }
.provider-validation-tool__region-option strong { overflow: hidden; color: var(--color-text-title, #1c1c26); font-size: 12px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.provider-validation-tool__region-option code { overflow: hidden; color: var(--color-text-secondary, #777786); font: 11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.provider-validation-tool__summary { display: grid; gap: 4px; margin: 0; }
.provider-validation-tool__summary span { color: var(--color-text-secondary, #777786); font-size: 11px; }
.provider-validation-tool__security-note { padding-left: 9px; border-left: 2px solid var(--color-primary, #6d5ef6); line-height: 1.45; }
.provider-validation-tool__retry { display: grid; gap: 10px; padding-top: 12px; border-top: 1px solid var(--color-border-light, #e6e7ee); }
.provider-validation-tool__retry h3 { margin: 0; color: var(--color-text-title, #1c1c26); font-size: 13px; font-weight: 650; }
.provider-validation-tool__results { max-height: 220px; overflow: auto; border: 1px solid var(--color-border-light, #e6e7ee); border-radius: 8px; background: #fff; }
.provider-validation-tool__results > div:last-child { border-bottom: 0; }
.provider-validation-tool__results > div { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px 8px; padding: 9px 10px; border-bottom: 1px solid var(--color-border-light, #ededf3); }
.provider-validation-tool__results > div > div { display: grid; gap: 3px; min-width: 0; }
.provider-validation-tool__results span { color: var(--color-text-secondary, #777786); font-size: 11px; }
.provider-validation-tool__results p { grid-column: 1 / -1; margin: 0; overflow: hidden; color: var(--el-color-danger, #f56c6c); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.provider-validation-tool__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: auto; padding-top: 4px; }
.provider-validation-tool__actions :deep(.el-button + .el-button) { margin-left: 0; }
.provider-validation-tool__error { flex: 0 0 auto; }
.provider-validation-tool__empty { display: grid; min-height: 240px; place-items: center; }
.provider-import-page :deep(.fullscreen-form-footer) { position: absolute; right: 0; bottom: 0; left: 0; z-index: 1; box-sizing: border-box; display: flex; align-items: center; min-height: 72px; padding: 12px max(28px, calc((100% - 1600px) / 2)); border-top: 1px solid #e5e6eb; background: rgb(255 255 255 / 96%); box-shadow: 0 -4px 16px rgb(29 33 41 / 6%); }
.provider-import-footer__actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; width: 100%; }
.provider-import-footer__actions :deep(.el-button + .el-button) { margin-left: 0; }
@media (min-width: 1024px) { .provider-import-layout { flex-direction: row; } }
@media (max-width: 1199px) { .provider-import-workspace--with-tool { grid-template-columns: 1fr; overflow: auto; } .provider-validation-tool { min-height: 440px; border-top: 1px solid var(--color-border-light, #e6e7ee); border-left: 0; } }
@media (max-width: 720px) { .storage-providers-page { padding: 12px; } .storage-providers-page__header { align-items: flex-start; flex-direction: column; } .storage-providers-page__actions { justify-content: flex-start; } .storage-providers-page__credentials { grid-template-columns: 1fr; } .storage-provider-drawer__sections { --storage-provider-regions-table-max-height: clamp(240px, calc(100dvh - 540px), 360px); } .storage-provider-drawer__run-summary a { width: 100%; margin-left: 0; } .provider-import-page { padding: 18px 12px calc(80px + var(--app-safe-bottom)); } .provider-import-layout { gap: 16px; } .provider-import-content, .provider-validation-tool { padding: 16px; } .provider-import-page :deep(.fullscreen-form-footer) { min-height: 64px; padding: 10px 12px; } }
</style>
