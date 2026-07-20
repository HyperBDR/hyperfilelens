import { computed, reactive, ref, watch, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { apiErrorMessage } from '../lib/api'
import { openErrorDetails } from '../lib/errors/details'
import { aiProviderLabel } from '../lib/aiProviderDisplay'
import { defaultAiModelDisplayName } from '../lib/aiModelDisplay'
import {
  capabilityClass,
  normalizeCapabilities,
  type AiCatalogCapability,
} from '../lib/aiModelCapabilities'
import {
  createLensModel,
  fetchLensModelCatalog,
  fetchLensModelDetail,
  fetchLensModelProviders,
  testLensModel,
  updateLensModel,
} from '../lib/lensApi'

export type AiCatalogModel = {
  id: string
  label?: string
  name?: string
  capabilities?: AiCatalogCapability[]
  max_input_tokens?: number
  max_output_tokens?: number
  reference_pricing?: {
    input_usd_per_1m?: number | null
    output_usd_per_1m?: number | null
  } | null
}

export type AiCatalogProvider = {
  id: string
  label?: string
  name?: string
  default_api_base?: string | null
  models?: AiCatalogModel[]
}

type ProviderSchemaEntry = {
  default_api_base?: string
  default_model?: string
  required?: string[]
  optional?: string[]
}

function providerDisplayName(row: AiCatalogProvider) {
  return row.label || row.name || aiProviderLabel(row.id, row.id)
}

export function useAiModelForm(editingUuid: Ref<string | null>) {
  const { t } = useI18n()

  const loading = ref(false)
  const saving = ref(false)
  const testing = ref(false)
  const testOk = ref<boolean | null>(null)
  const testDetail = ref('')
  const modelDropdownOpen = ref(false)
  const useCustomModel = ref(false)
  const nameTouched = ref(false)

  const providers = ref<AiCatalogProvider[]>([])
  const capabilityLabels = ref<Record<string, string>>({})
  const providerSchemas = ref<Record<string, ProviderSchemaEntry>>({})

  const form = reactive({
    name: '',
    provider: '',
    model: '',
    api_key: '',
    api_base: '',
    is_active: true,
  })

  const isEditing = computed(() => Boolean(editingUuid.value))

  const currentProvider = computed(() =>
    providers.value.find((p) => p.id === form.provider) ?? null,
  )

  const currentProviderModels = computed(() => currentProvider.value?.models ?? [])

  const selectedModelInfo = computed(() => {
    const modelId = form.model.trim()
    if (!modelId) return null
    const row = currentProviderModels.value.find((m) => m.id === modelId)
    if (!row) return null
    return {
      capabilities: normalizeCapabilities(row.capabilities),
      max_input_tokens: row.max_input_tokens,
      max_output_tokens: row.max_output_tokens,
      reference_pricing: row.reference_pricing,
    }
  })

  const modelSelectLabel = computed(() => {
    if (useCustomModel.value) {
      return form.model.trim()
        ? `${t('insight.aiSettings.modelCustom')} · ${form.model.trim()}`
        : t('insight.aiSettings.modelCustom')
    }
    const row = currentProviderModels.value.find((m) => m.id === form.model)
    return row?.label || row?.name || row?.id || t('insight.aiSettings.modelSelect')
  })

  function capabilityLabel(key: string) {
    return capabilityLabels.value[key] || key
  }

  function suggestedDisplayName() {
    const providerRow = currentProvider.value
    const providerLabel = providerRow ? providerDisplayName(providerRow) : aiProviderLabel(form.provider, form.provider)
    const modelId = form.model.trim()
    if (!providerLabel && !modelId) return ''
    if (!modelId) return providerLabel
    if (useCustomModel.value) {
      return defaultAiModelDisplayName(form.provider, modelId, providerLabel, modelId)
    }
    const row = currentProviderModels.value.find((m) => m.id === modelId)
    const modelLabel = row?.label || row?.name || modelId
    return defaultAiModelDisplayName(form.provider, modelId, providerLabel, modelLabel)
  }

  function syncSuggestedName() {
    if (nameTouched.value) return
    form.name = suggestedDisplayName()
  }

  function onNameInput() {
    nameTouched.value = true
  }

  function resetNameAutoFill() {
    nameTouched.value = false
    syncSuggestedName()
  }

  function resetForm() {
    form.name = ''
    form.provider = providers.value[0]?.id || ''
    form.model = ''
    form.api_key = ''
    form.api_base = ''
    form.is_active = true
    useCustomModel.value = false
    nameTouched.value = false
    testOk.value = null
    testDetail.value = ''
    applyProviderDefaults(form.provider)
    syncSuggestedName()
  }

  function applyProviderDefaults(providerId: string) {
    if (!providerId || isEditing.value) return
    const schema = providerSchemas.value[providerId]
    const provider = providers.value.find((p) => p.id === providerId)
    const defaultBase = provider?.default_api_base || schema?.default_api_base || ''
    if (defaultBase) form.api_base = defaultBase
    if (schema?.default_model && !form.model) form.model = schema.default_model
  }

  function selectProvider(providerId: string) {
    if (isEditing.value) return
    form.provider = providerId
    form.model = ''
    useCustomModel.value = false
    testOk.value = null
    testDetail.value = ''
    applyProviderDefaults(providerId)
    resetNameAutoFill()
  }

  function selectModel(modelId: string) {
    modelDropdownOpen.value = false
    if (modelId === '__custom__') {
      useCustomModel.value = true
      form.model = ''
      resetNameAutoFill()
      return
    }
    useCustomModel.value = false
    form.model = modelId
    resetNameAutoFill()
  }

  async function loadCatalog() {
    const [catalogRaw, providersRaw] = await Promise.all([
      fetchLensModelCatalog(),
      fetchLensModelProviders().catch(() => null),
    ])

    if (catalogRaw && typeof catalogRaw === 'object') {
      const catalog = catalogRaw as {
        providers?: AiCatalogProvider[]
        capability_labels?: Record<string, string>
      }
      providers.value = (catalog.providers ?? []).map((row) => ({
        ...row,
        label: providerDisplayName(row),
        models: (row.models ?? []).map((m) => ({
          ...m,
          label: m.label || m.name || m.id,
        })),
      }))
      capabilityLabels.value = catalog.capability_labels ?? {}
    } else if (Array.isArray(catalogRaw)) {
      providers.value = catalogRaw as AiCatalogProvider[]
    } else {
      providers.value = []
    }

    if (providersRaw && typeof providersRaw === 'object') {
      const schemaObj = providersRaw as { providers?: Record<string, ProviderSchemaEntry> }
      if (schemaObj.providers && typeof schemaObj.providers === 'object') {
        providerSchemas.value = schemaObj.providers
      } else if (Array.isArray(providersRaw)) {
        providerSchemas.value = Object.fromEntries(
          (providersRaw as { id: string }[]).map((row) => [row.id, {}]),
        )
      }
    }
  }

  async function loadEditing() {
    if (!editingUuid.value) {
      resetForm()
      return
    }
    const detail = await fetchLensModelDetail(editingUuid.value)
    form.provider = detail.provider || ''
    form.model = detail.config?.model || ''
    form.name = detail.name?.trim() || ''
    form.api_key = ''
    form.api_base = detail.config?.api_base || ''
    form.is_active = detail.is_active !== false
    nameTouched.value = Boolean(form.name)
    if (!form.name) syncSuggestedName()
    const inList = currentProviderModels.value.some((m) => m.id === form.model)
    useCustomModel.value = Boolean(form.model) && !inList
  }

  function modelCapabilities(model: AiCatalogModel) {
    return normalizeCapabilities(model.capabilities)
  }

  watch(
    () => form.provider,
    (next, prev) => {
      if (!next || next === prev || isEditing.value) return
      form.model = ''
      useCustomModel.value = false
      testOk.value = null
      testDetail.value = ''
      applyProviderDefaults(next)
      resetNameAutoFill()
    },
  )

  watch(
    () => form.model,
    () => {
      if (isEditing.value && nameTouched.value) return
      syncSuggestedName()
    },
  )

  async function init() {
    loading.value = true
    try {
      await loadCatalog()
      await loadEditing()
      if (!editingUuid.value && !form.provider && providers.value[0]) {
        selectProvider(providers.value[0].id)
      }
    } catch (err) {
      ElMessage.error({ message: apiErrorMessage(err, t('errors.generic.loadFailed')), grouping: true })
    } finally {
      loading.value = false
    }
  }

  function buildPayload() {
    const config: Record<string, string> = {
      model: form.model.trim(),
    }
    if (form.api_base.trim()) config.api_base = form.api_base.trim()
    if (form.api_key.trim()) config.api_key = form.api_key.trim()
    return {
      name: form.name.trim(),
      provider: form.provider,
      config,
      is_active: form.is_active,
    }
  }

  async function runTest() {
    if (!form.provider || !form.model.trim()) {
      ElMessage.warning({ message: t('insight.aiSettings.testNeedModel'), grouping: true })
      return false
    }
    testing.value = true
    testOk.value = null
    testDetail.value = ''
    try {
      const res = await testLensModel(buildPayload())
      const ok = (res as { ok?: boolean }).ok ?? (res as { success?: boolean }).success ?? true
      testOk.value = ok
      testDetail.value =
        (res as { message?: string }).message ||
        (res as { detail?: string }).detail ||
        (ok ? t('insight.aiSettings.connectivityOk') : t('insight.aiSettings.connectivityFail', { detail: '' }))
      if (ok) {
        ElMessage.success({ message: t('insight.aiSettings.connectivityOk'), grouping: true })
      } else {
        openErrorDetails({
          error: res,
          overrides: {
            title: t('insight.aiSettings.connectivityFail', { detail: '' }),
            summary: testDetail.value,
            issue: testDetail.value,
            rawDetail: res,
          },
        })
      }
      return ok
    } catch (err) {
      testOk.value = false
      testDetail.value = apiErrorMessage(err, t('insight.aiSettings.connectivityFail', { detail: '' }))
      openErrorDetails({
        error: err,
        overrides: {
          title: t('insight.aiSettings.connectivityFail', { detail: '' }),
          summary: testDetail.value,
          issue: testDetail.value,
        },
      })
      return false
    } finally {
      testing.value = false
    }
  }

  async function submit() {
    if (!form.provider || !form.model.trim()) {
      ElMessage.warning({ message: t('insight.aiSettings.formRequired'), grouping: true })
      return false
    }
    if (!form.name.trim()) {
      syncSuggestedName()
    }
    if (!form.name.trim()) {
      ElMessage.warning({ message: t('insight.aiSettings.nameRequired'), grouping: true })
      return false
    }
    if (!editingUuid.value && !form.api_key.trim()) {
      ElMessage.warning({ message: t('insight.aiSettings.apiKeyRequired'), grouping: true })
      return false
    }
    saving.value = true
    try {
      if (editingUuid.value) {
        await updateLensModel(editingUuid.value, buildPayload())
      } else {
        await createLensModel(buildPayload())
      }
      ElMessage.success({ message: t('insight.aiSettings.saveSuccess'), grouping: true })
      return true
    } catch (err) {
      ElMessage.error({ message: apiErrorMessage(err, t('errors.generic.requestFailed')), grouping: true })
      return false
    } finally {
      saving.value = false
    }
  }

  return {
    loading,
    saving,
    testing,
    testOk,
    testDetail,
    modelDropdownOpen,
    useCustomModel,
    providers,
    form,
    isEditing,
    currentProvider,
    currentProviderModels,
    selectedModelInfo,
    modelSelectLabel,
    capabilityLabel,
    capabilityClass,
    selectProvider,
    selectModel,
    onNameInput,
    init,
    runTest,
    submit,
    modelCapabilities,
  }
}
