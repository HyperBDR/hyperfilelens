<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import {
  CloudCog,
  Download,
  FileJson,
  RefreshCw,
  RotateCcw,
  Search,
  Upload,
} from 'lucide-vue-next'
import JsonCodeEditor from '../../../components/JsonCodeEditor.vue'
import HflTablePanel from '../../../components/HflTablePanel.vue'
import ModulePage from '../../../components/ModulePage.vue'
import { useResponsiveDrawerWidth } from '../../../composables/useResponsiveDrawerWidth'
import { apiErrorMessage } from '../../../lib/api'
import {
  applyProviderImport,
  cancelProviderValidationRun,
  confirmProviderReset,
  createProviderValidationRun,
  diffProviderImport,
  exportProviders,
  fetchPlatformStorageProviders,
  normalizedStorageProviderSnapshot,
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
} from '../../../lib/storageProviderCatalogApi'
import PlatformOpsDetailSection from '../../components/PlatformOpsDetailSection.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import ProviderDiffDetails from './ProviderDiffDetails.vue'

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
let pollTimer: number | null = null

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
    if (providerDetailsOpen.value && !selectedProvider.value) providerDetailsOpen.value = false
  } catch (error) {
    loadError.value = apiErrorMessage(error, t('platformOps.storageProviders.loadFailed'))
  } finally {
    if (!quiet) loading.value = false
  }
}

watch(hasActiveRun, (active) => {
  if (active && pollTimer === null) {
    pollTimer = window.setInterval(() => void load({ quiet: true }), 3000)
  } else if (!active && pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}, { immediate: true })

onMounted(load)
onBeforeUnmount(() => {
  if (pollTimer !== null) window.clearInterval(pollTimer)
  clearSecrets()
})

// Import Edit -> Review -> Apply flow.
type ImportCredential = { access_key_id: string; secret_access_key: string }
const importOpen = ref(false)
const importStep = ref<'editing' | 'reviewing' | 'success'>('editing')
const importContent = ref('')
const importPreview = ref<ProviderImportPreview | null>(null)
const importReview = ref<ProviderImportReview | null>(null)
const importError = ref('')
const riskConfirmations = ref<string[]>([])
const importCredentials = reactive<Record<string, ImportCredential>>({})
const importRegionIds = reactive<Record<string, string[]>>({})
const importRuns = reactive<Record<string, ProviderValidationRun>>({})
const validationSnapshots = reactive<Record<string, string>>({})
const validationLoading = reactive<Record<string, boolean>>({})

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

watch(parsedImportProviders, (items) => {
  for (const provider of items) {
    importCredentials[provider.id] ||= { access_key_id: '', secret_access_key: '' }
    const available = new Set(provider.regions.map((region) => region.id))
    importRegionIds[provider.id] = (importRegionIds[provider.id] || [])
      .filter((regionId) => available.has(regionId))
  }
}, { flush: 'sync' })

function importValidationStatus(provider: StorageProviderConfig) {
  const run = importRuns[provider.id] || runByProvider.value[provider.id]
  if (!run) return 'not_run'
  const snapshot = normalizedStorageProviderSnapshot(provider)
  if (validationSnapshots[provider.id] && validationSnapshots[provider.id] !== snapshot) return 'stale'
  if (run.candidate_config && normalizedStorageProviderSnapshot(run.candidate_config) !== snapshot) return 'stale'
  if (run.status === 'passed') return `passed_${run.coverage || 'partial'}`
  return run.status
}

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
    validationSnapshots[provider.id] = normalizedStorageProviderSnapshot(provider)
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

function resetImportReview() {
  importPreview.value = null
  importReview.value = null
  riskConfirmations.value = []
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
  importReview.value = null
  riskConfirmations.value = []
  importOpen.value = true
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
  } catch (error) {
    importError.value = apiErrorMessage(error, t('platformOps.storageProviders.invalidJson'))
  } finally {
    actionLoading.value = false
  }
}

async function validateImportProviders() {
  actionLoading.value = true
  try {
    const candidates = parsedImportProviders.value.filter((provider) => {
      const count = importRegionIds[provider.id]?.length || 0
      return count >= 1 && count <= 10
    })
    if (!candidates.length) throw new Error(t('platformOps.storageProviders.noValidationCandidates'))
    const results = await Promise.allSettled(
      candidates.map((provider) => validateImportProvider(provider, false)),
    )
    const failures = results.filter((result) => result.status === 'rejected')
    if (failures.length) {
      ElMessage.warning(t('platformOps.storageProviders.validationPartial', { count: failures.length }))
    } else {
      ElMessage.success(t('platformOps.storageProviders.validationQueued'))
    }
    await load({ quiet: true })
  } catch (error) {
    importError.value = apiErrorMessage(error, t('platformOps.storageProviders.actionFailed'))
  } finally {
    clearSecrets()
    actionLoading.value = false
  }
}

async function nextImport() {
  actionLoading.value = true
  try {
    importReview.value = await reviewProviderImport(importContent.value)
    riskConfirmations.value = []
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
    await applyProviderImport(importContent.value, importReview.value, riskConfirmations.value)
    importStep.value = 'success'
    ElMessage.success(t('platformOps.storageProviders.applySuccess'))
    await load()
  } catch (error) {
    importError.value = apiErrorMessage(error, t('platformOps.storageProviders.actionFailed'))
  } finally {
    actionLoading.value = false
  }
}

function allRisksConfirmed() {
  const required = importReview.value?.required_risk_confirmation_ids || []
  return required.every((id) => riskConfirmations.value.includes(id))
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
            <el-table-column :label="t('platformOps.storageProviders.provider')" min-width="300">
              <template #default="{ row }">
                <button type="button" class="storage-providers-page__title-button" @click.stop="openProviderDetails(row)">{{ row.display_name }}</button>
                <small>{{ row.id }}</small>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.storageProviders.sourceLabel')" min-width="180">
              <template #default="{ row }"><el-tag size="small" effect="plain">{{ providerSourceLabel(row.source) }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="region_count" :label="t('platformOps.storageProviders.regions')" width="110" />
            <el-table-column :label="t('platformOps.storageProviders.validation')" min-width="180">
              <template #default="{ row }">
                <el-tag v-if="runByProvider[row.id]" size="small" :type="statusType(runByProvider[row.id].status)">{{ statusLabel(runByProvider[row.id].status) }}</el-tag>
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('platformOps.storageProviders.actions')" width="110" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" :disabled="row.source !== 'override'" @click.stop="openReset(row.id)">{{ t('platformOps.storageProviders.reset') }}</el-button>
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
              <span class="hfl-detail-row__value">{{ selectedProvider.updated_at || '—' }}</span>
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
          <el-table :data="filteredRegions" stripe max-height="420" class="storage-provider-drawer__regions-table" empty-text="—">
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

    <el-dialog v-model="importOpen" :title="t('platformOps.storageProviders.importTitle')" width="min(1080px, 96vw)" destroy-on-close @closed="clearSecrets">
      <el-steps :active="importStep === 'editing' ? 0 : importStep === 'reviewing' ? 1 : 2" finish-status="success" simple>
        <el-step :title="t('platformOps.storageProviders.editConfiguration')" />
        <el-step :title="t('platformOps.storageProviders.review')" />
        <el-step :title="t('platformOps.storageProviders.done')" />
      </el-steps>
      <template v-if="importStep === 'editing'">
        <div class="storage-providers-page__editor-toolbar">
          <label class="el-button"><FileJson :size="15" />{{ t('platformOps.storageProviders.uploadJson') }}<input type="file" accept="application/json,.json" hidden @change="uploadImport" /></label>
          <el-button @click="formatImport">{{ t('platformOps.storageProviders.formatJson') }}</el-button>
        </div>
        <JsonCodeEditor :model-value="importContent" :aria-label="t('platformOps.storageProviders.catalogEditor')" @update:model-value="setImportContent" />
        <el-alert v-if="importError" type="error" :title="importError" show-icon :closable="false" />
        <section v-if="parsedImportProviders.length" class="storage-providers-page__validation-cards">
          <article v-for="provider in parsedImportProviders" :key="provider.id">
            <header><strong>{{ provider.display_name || provider.id }}</strong><el-tag size="small" :type="statusType(importValidationStatus(provider))">{{ statusLabel(importValidationStatus(provider)) }}</el-tag></header>
            <template>
              <el-select
                v-model="importRegionIds[provider.id]"
                multiple
                collapse-tags
                collapse-tags-tooltip
                :max-collapse-tags="3"
                :multiple-limit="10"
                :placeholder="t('platformOps.storageProviders.selectValidationRegions')"
              >
                <el-option
                  v-for="region in provider.regions"
                  :key="region.id"
                  :label="`${region.display_name} (${region.id})`"
                  :value="region.id"
                />
              </el-select>
              <small>{{ t('platformOps.storageProviders.selectedRegionLimit') }}</small>
              <el-input v-model="importCredentials[provider.id].access_key_id" autocomplete="off" :placeholder="t('platformOps.storageProviders.accessKeyId')" />
              <el-input v-model="importCredentials[provider.id].secret_access_key" type="password" autocomplete="new-password" show-password :placeholder="t('platformOps.storageProviders.secretAccessKey')" />
              <div class="storage-providers-page__validation-actions">
                <el-button
                  v-if="!importRun(provider.id) || ['passed', 'cancelled', 'expired'].includes(importRun(provider.id)!.status)"
                  type="primary"
                  :disabled="!importRegionIds[provider.id]?.length"
                  :loading="validationLoading[provider.id]"
                  @click="validateImportProvider(provider)"
                >{{ t('platformOps.storageProviders.validateProvider') }}</el-button>
                <el-button
                  v-if="importRun(provider.id) && activeStatuses.includes(importRun(provider.id)!.status)"
                  type="danger"
                  plain
                  :loading="validationLoading[provider.id]"
                  @click="cancelImportValidation(provider)"
                >{{ t('common.stop') }}</el-button>
                <el-button
                  v-if="['validation_failed', 'cleanup_required'].includes(importRun(provider.id)?.status || '')"
                  type="warning"
                  :loading="validationLoading[provider.id]"
                  @click="retryImportValidation(provider)"
                >{{ t('platformOps.storageProviders.retryValidation') }}</el-button>
              </div>
            </template>
          </article>
        </section>
        <ProviderDiffDetails v-if="importPreview" :diffs="importPreview.providers" />
      </template>
      <template v-else-if="importStep === 'reviewing' && importReview">
        <el-alert type="info" :title="t('platformOps.storageProviders.reviewReadonly')" show-icon :closable="false" />
        <ProviderDiffDetails :diffs="importReview.providers" />
        <section class="storage-providers-page__review-evidence">
          <div v-for="evidence in importReview.validation_evidence" :key="evidence.provider_id"><strong>{{ evidence.provider_id }}</strong><el-tag :type="statusType(evidence.status)">{{ statusLabel(evidence.status) }}</el-tag></div>
        </section>
        <el-checkbox-group v-model="riskConfirmations" class="storage-providers-page__risks">
          <el-checkbox v-for="risk in importReview.required_risk_confirmation_ids" :key="risk" :value="risk">{{ t('platformOps.storageProviders.confirmRisk', { risk }) }}</el-checkbox>
        </el-checkbox-group>
        <el-alert v-if="importError" type="error" :title="importError" show-icon :closable="false" />
      </template>
      <el-result v-else icon="success" :title="t('platformOps.storageProviders.applySuccess')" :sub-title="t('platformOps.storageProviders.applySuccessHint')" />
      <template #footer>
        <el-button @click="importOpen = false">{{ importStep === 'success' ? t('common.close') : t('common.cancel') }}</el-button>
        <template v-if="importStep === 'editing'">
          <el-button :loading="actionLoading" @click="validateImportProviders">{{ t('platformOps.storageProviders.validate') }}</el-button>
          <el-button :loading="actionLoading" @click="previewImport">{{ t('platformOps.storageProviders.diff') }}</el-button>
          <el-button type="primary" :loading="actionLoading" @click="nextImport">{{ t('common.next') }}</el-button>
        </template>
        <template v-else-if="importStep === 'reviewing'">
          <el-button @click="importStep = 'editing'">{{ t('common.back') }}</el-button>
          <el-button type="primary" :disabled="!allRisksConfirmed()" :loading="actionLoading" @click="applyImport">{{ t('platformOps.storageProviders.apply') }}</el-button>
        </template>
      </template>
    </el-dialog>

    <el-dialog v-model="resetOpen" :title="t('platformOps.storageProviders.resetTitle')" width="min(720px, 92vw)">
      <el-alert type="warning" :title="t('platformOps.storageProviders.resetWarning')" show-icon :closable="false" />
      <ProviderDiffDetails v-if="resetReview" :diffs="resetReview.providers" />
      <template #footer><el-button @click="resetOpen = false">{{ t('common.cancel') }}</el-button><el-button type="danger" :loading="actionLoading" @click="confirmReset">{{ t('platformOps.storageProviders.confirmReset') }}</el-button></template>
    </el-dialog>
  </ModulePage>
</template>

<style scoped>
.storage-providers-page { display: flex; min-height: 0; flex: 1; flex-direction: column; gap: 14px; padding: 18px; overflow: hidden; }
.storage-providers-page__header, .storage-providers-page__actions, .storage-providers-page__run-head, .storage-providers-page__editor-toolbar { display: flex; align-items: center; gap: 10px; }
.storage-providers-page__header { justify-content: space-between; }
.storage-providers-page__header p { margin: 0; color: var(--color-text-secondary, #70707e); font-size: 13px; }
.storage-providers-page__actions { flex-wrap: wrap; justify-content: flex-end; }
.storage-providers-page__actions :deep(.el-button span), .storage-providers-page__editor-toolbar .el-button { gap: 6px; }
.storage-providers-page :deep(.hfl-list-panel) { flex: 1 1 auto; min-height: 0; }
.storage-providers-page small, .storage-provider-drawer small { display: block; margin-top: 3px; color: var(--color-text-secondary, #777786); font-size: 11px; }
.storage-providers-page__title-button { display: block; max-width: 100%; padding: 0; overflow: hidden; border: 0; background: transparent; color: var(--color-text-title, #1c1c26); cursor: pointer; font: inherit; font-weight: 600; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.storage-providers-page__title-button:hover, .storage-providers-page__title-button:focus-visible { color: var(--color-primary, #6d5ef6); outline: none; text-decoration: underline; text-underline-offset: 3px; }
.storage-provider-drawer__header, .storage-provider-drawer__identity, .storage-provider-drawer__run-summary { display: flex; align-items: center; gap: 10px; }
.storage-provider-drawer__header { width: 100%; min-width: 0; justify-content: space-between; }
.storage-provider-drawer__identity { min-width: 0; }
.storage-provider-drawer__identity > div { min-width: 0; }
.storage-provider-drawer__identity h2 { margin: 0; overflow: hidden; color: var(--color-text-title, #1c1c26); font-size: 18px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.storage-provider-drawer__identity p { margin: 4px 0 0; color: var(--color-text-secondary, #70707e); font: 12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.storage-provider-drawer__sections { padding-bottom: 8px; }
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
.storage-providers-page__validation-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
.storage-providers-page__validation-cards article { display: grid; gap: 8px; padding: 12px; border: 1px solid var(--color-border-light, #ededf3); border-radius: 9px; }
.storage-providers-page__validation-cards header, .storage-providers-page__review-evidence > div { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.storage-providers-page__validation-cards p { margin: 0; color: var(--color-text-secondary, #777786); font-size: 12px; }
.storage-providers-page__review-evidence { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 14px; }
.storage-providers-page__review-evidence > div { padding: 10px; border: 1px solid var(--color-border-light, #ededf3); border-radius: 8px; }
.storage-providers-page__risks { display: grid; margin-top: 12px; }
@media (max-width: 720px) { .storage-providers-page { padding: 12px; } .storage-providers-page__header { align-items: flex-start; flex-direction: column; } .storage-providers-page__actions { justify-content: flex-start; } .storage-providers-page__credentials, .storage-providers-page__validation-cards, .storage-providers-page__review-evidence { grid-template-columns: 1fr; } .storage-provider-drawer__run-summary a { width: 100%; margin-left: 0; } }
</style>
