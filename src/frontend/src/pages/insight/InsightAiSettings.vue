<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { lensModelsPath } from '../../lib/lensEngineRoutes'
import { useI18n } from 'vue-i18n'
import { ChevronDown, CirclePlay, CircleStop, Pencil, Plus, RefreshCw, Search, Star, Trash2 } from 'lucide-vue-next'
import { ElMessage, type ElTable } from 'element-plus'
import { useListTableLayout } from '../../composables/useListTableLayout'
import { useListSearch } from '../../composables/useListSearch'
import { apiErrorMessage } from '../../lib/api'
import {
  deleteLensModel,
  fetchLensHealth,
  listLensModels,
  patchLensModel,
  type LensHealth,
  type LensLlmConfig,
} from '../../lib/lensApi'
import { defaultAiModelDisplayName } from '../../lib/aiModelDisplay'
import { aiProviderLabel } from '../../lib/aiProviderDisplay'
import InsightAiModelDetailDrawer from './InsightAiModelDetailDrawer.vue'
import HflBooleanStatusTag from '../../components/HflBooleanStatusTag.vue'
import DangerConfirmDialog from '../../components/DangerConfirmDialog.vue'

const { t } = useI18n()
const router = useRouter()

const TABLE_HEADER_STYLE: Record<string, string> = {
  background: 'rgba(248, 250, 252, 0.96)',
  color: 'rgb(71 85 105)',
  fontWeight: '600',
  whiteSpace: 'nowrap',
}

const loading = ref(false)
const health = ref<LensHealth | null>(null)
const models = ref<LensLlmConfig[]>([])
const search = ref('')
const { appliedSearch, clearSearch } = useListSearch(search)
const selectedRows = ref<LensLlmConfig[]>([])
const moreActionsOpen = ref(false)
const detailOpen = ref(false)
const detailUuid = ref<string | null>(null)
const deleteOpen = ref(false)
const deleteLoading = ref(false)
const deleteTarget = ref<LensLlmConfig | null>(null)
const detailRefreshToken = ref(0)

const tableRef = ref<InstanceType<typeof ElTable> | null>(null)
const tableBlockRef = ref<HTMLElement | null>(null)
const { tableMaxHeight, layoutTable, handleTableScroll } = useListTableLayout(tableRef, tableBlockRef)

const bridgeReady = computed(
  () => health.value?.lens?.configured && health.value?.lens?.authenticated,
)

const filteredModels = computed(() => {
  const q = appliedSearch.value.trim().toLowerCase()
  if (!q) return models.value
  return models.value.filter((row) => {
    const hay = [
      row.provider,
      row.name,
      row.config?.model,
      row.config?.api_base,
      row.uuid,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return hay.includes(q)
  })
})

const batchDisabled = computed(() => selectedRows.value.length === 0)
const singleSelected = computed(() => selectedRows.value.length === 1 ? selectedRows.value[0]! : null)
const selectedIsManaged = computed(() => Boolean(singleSelected.value?.deployment_managed))
const selectedCanSetDefault = computed(() => Boolean(
  singleSelected.value &&
  singleSelected.value.is_active !== false &&
  !singleSelected.value.is_default,
))

function modelName(row: LensLlmConfig) {
  if (row.name?.trim()) return row.name.trim()
  const provider = row.provider || 'provider'
  const model = row.config?.model || '—'
  return defaultAiModelDisplayName(
    provider,
    model,
    aiProviderLabel(provider, provider),
    model,
  )
}

async function load() {
  loading.value = true
  try {
    health.value = await fetchLensHealth()
    if (health.value.lens?.configured && health.value.lens?.authenticated) {
      models.value = await listLensModels()
    } else {
      models.value = []
    }
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('errors.generic.loadFailed')), grouping: true })
  } finally {
    loading.value = false
    if (detailOpen.value) detailRefreshToken.value += 1
    layoutTable()
  }
}

function openCreate() {
  router.push(lensModelsPath() + '/add')
}

function openDetail(row: LensLlmConfig) {
  detailUuid.value = row.uuid
  detailOpen.value = true
}

function openEdit(row: LensLlmConfig | string) {
  const uuid = typeof row === 'string' ? row : row.uuid
  router.push(`${lensModelsPath()}/${uuid}/edit`)
}

function onSelectionChange(rows: LensLlmConfig[]) {
  selectedRows.value = rows
}

async function setActive(row: LensLlmConfig, isActive: boolean) {
  if (row.deployment_managed) return
  if (row.is_active === isActive) return
  try {
    await patchLensModel(row.uuid, { is_active: isActive })
    ElMessage.success({ message: t('insight.aiSettings.saveSuccess'), grouping: true })
    await load()
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('errors.generic.requestFailed')), grouping: true })
  }
}

async function setDefault(row: LensLlmConfig) {
  if (row.is_default || row.is_active === false) return
  try {
    await patchLensModel(row.uuid, { is_default: true })
    ElMessage.success({ message: t('insight.aiSettings.defaultModelSaved'), grouping: true })
    await load()
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('errors.generic.requestFailed')), grouping: true })
  }
}

function deleteRow(row: LensLlmConfig) {
  deleteTarget.value = row
  deleteOpen.value = true
}

async function confirmDelete() {
  const row = deleteTarget.value
  if (!row) return
  deleteLoading.value = true
  try {
    await deleteLensModel(row.uuid)
    ElMessage.success({ message: t('insight.aiSettings.deleteSuccess'), grouping: true })
    selectedRows.value = []
    await load()
    deleteOpen.value = false
    deleteTarget.value = null
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('errors.generic.requestFailed')), grouping: true })
  } finally {
    deleteLoading.value = false
  }
}

async function deleteSelected() {
  const row = singleSelected.value
  if (!row || row.deployment_managed) return
  await deleteRow(row)
}

async function enableSelected() {
  const row = singleSelected.value
  if (!row || row.deployment_managed) return
  await setActive(row, true)
}

async function disableSelected() {
  const row = singleSelected.value
  if (!row || row.deployment_managed) return
  await setActive(row, false)
}

function editSelected() {
  const row = singleSelected.value
  if (!row || row.deployment_managed) return
  openEdit(row)
}

async function setSelectedDefault() {
  const row = singleSelected.value
  if (!row) return
  await setDefault(row)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="hfl-list-shell hfl-list-shell--fill">
    <div class="hfl-list-panel hfl-list-panel--fill">
      <div class="hfl-list-toolbar">
        <ElButton type="primary" :disabled="!bridgeReady" @click="openCreate">
          <Plus :size="16" />
          {{ t('insight.aiSettings.btnAdd') }}
        </ElButton>

        <ElDropdown
          trigger="click"
          popper-class="hfl-actions-dropdown"
          @visible-change="moreActionsOpen = $event"
        >
          <ElButton :disabled="!bridgeReady">
            {{ t('insight.aiSettings.btnMoreActions') }}
            <ChevronDown
              :size="16"
              class="hfl-list-more__chev"
              :class="{ 'hfl-list-more__chev--open': moreActionsOpen }"
            />
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem :disabled="batchDisabled || !singleSelected || selectedIsManaged" @click="editSelected">
                <span class="el-dropdown-menu__item-content">
                  <Pencil :size="14" class="shrink-0" />
                  <span>{{ t('common.edit') }}</span>
                </span>
              </ElDropdownItem>
              <ElDropdownItem :disabled="!selectedCanSetDefault" @click="setSelectedDefault">
                <span class="el-dropdown-menu__item-content">
                  <Star :size="14" class="shrink-0" />
                  <span>{{ t('insight.aiSettings.setDefault') }}</span>
                </span>
              </ElDropdownItem>
              <ElDropdownItem divided :disabled="batchDisabled || !singleSelected || selectedIsManaged" @click="enableSelected">
                <span class="el-dropdown-menu__item-content">
                  <CirclePlay :size="14" class="shrink-0" />
                  <span>{{ t('insight.aiSettings.enable') }}</span>
                </span>
              </ElDropdownItem>
              <ElDropdownItem :disabled="batchDisabled || !singleSelected || selectedIsManaged" @click="disableSelected">
                <span class="el-dropdown-menu__item-content">
                  <CircleStop :size="14" class="shrink-0" />
                  <span>{{ t('insight.aiSettings.disable') }}</span>
                </span>
              </ElDropdownItem>
              <ElDropdownItem
                divided
                class="el-dropdown-menu__item--danger"
                :disabled="batchDisabled || !singleSelected || selectedIsManaged"
                @click="deleteSelected"
              >
                <span class="el-dropdown-menu__item-content">
                  <Trash2 :size="14" class="shrink-0" />
                  <span>{{ t('common.delete') }}</span>
                </span>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <div class="hfl-list-toolbar__right">
          <ElInput
            v-model="search"
            clearable
            size="small"
            :placeholder="t('insight.aiSettings.searchPlaceholder')"
            class="hfl-list-search"
            @clear="clearSearch"
          >
            <template #prefix>
              <Search :size="16" class="hfl-list-search__icon" />
            </template>
          </ElInput>
          <ElButton
            class="hfl-refresh-button"
            :title="t('common.refresh')"
            :disabled="loading"
            @click="load"
          >
            <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
          </ElButton>
        </div>
      </div>

      <div ref="tableBlockRef" class="hfl-list-table-block">
        <el-table
          ref="tableRef"
          v-table-overflow-title
          v-loading="loading"
          row-key="uuid"
          :data="filteredModels"
          stripe
          class="hfl-list-table"
          :max-height="tableMaxHeight"
          :header-cell-style="TABLE_HEADER_STYLE"
          @scroll="handleTableScroll"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" width="35" fixed="left" />
          <el-table-column
            :label="t('insight.aiSettings.colName')"
            min-width="220"
            fixed="left"
            class-name="hfl-table-name-col"
          >
            <template #default="{ row }">
              <div class="insight-ai-models-name">
                <button type="button" class="hfl-table-name-link hfl-table-name-link--full" @click="openDetail(row)">
                  {{ modelName(row) }}
                </button>
                <div v-if="row.is_default || row.deployment_managed" class="insight-ai-models-badges">
                  <ElTag v-if="row.is_default" size="small" type="success" effect="plain">
                    {{ t('insight.aiSettings.defaultBadge') }}
                  </ElTag>
                  <ElTag v-if="row.deployment_managed" size="small" type="info" effect="plain">
                    {{ t('insight.aiSettings.deploymentManagedBadge') }}
                  </ElTag>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="t('insight.aiSettings.labelProvider')" min-width="120">
            <template #default="{ row }">{{ row.provider || row.name || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('insight.aiSettings.labelModel')" min-width="160">
            <template #default="{ row }">{{ row.config?.model || '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('insight.aiSettings.labelApiBase')" min-width="200">
            <template #default="{ row }">
              <span class="insight-ai-models-mono">{{ row.config?.api_base || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('insight.aiSettings.labelActive')" width="110">
            <template #default="{ row }">
              <HflBooleanStatusTag
                :value="row.is_active !== false"
                :label="row.is_active !== false
                  ? t('insight.aiSettings.statusActive')
                  : t('insight.aiSettings.statusInactive')"
              />
            </template>
          </el-table-column>
          <template #empty>
            <el-empty
              :description="bridgeReady ? t('insight.aiSettings.emptyModels') : t('insight.shared.bridgeNotReady')"
              :image-size="80"
            />
          </template>
        </el-table>
      </div>
    </div>

    <InsightAiModelDetailDrawer
      v-model="detailOpen"
      :model-uuid="detailUuid"
      :refresh-token="detailRefreshToken"
      @edit="openEdit"
    />
    <DangerConfirmDialog
      v-model="deleteOpen"
      :title="t('insight.aiSettings.deleteTitle')"
      :message="deleteTarget ? t('insight.aiSettings.deleteConfirm', { name: modelName(deleteTarget) }) : ''"
      :items="deleteTarget ? [{ key: deleteTarget.uuid, name: modelName(deleteTarget) }] : []"
      :cancel-text="t('common.cancel')"
      :confirm-text="t('common.delete')"
      :loading="deleteLoading"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<style scoped>
.insight-ai-models-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.insight-ai-models-name {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 5px;
}

.insight-ai-models-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
