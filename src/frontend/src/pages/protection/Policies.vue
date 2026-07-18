<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ChevronDown, CirclePlay, CircleStop, Plus, RefreshCw, Search, SquarePen, Trash2 } from 'lucide-vue-next'
import PolicyDetailBasicPanel from './components/PolicyDetailBasicPanel.vue'
import FileFilterDetailBasicPanel from './components/FileFilterDetailBasicPanel.vue'
import HflPopover from '../../components/HflPopover.vue'
import { ElMessage, type ElTable } from 'element-plus'
import ModulePage from '../../components/ModulePage.vue'
import HflTablePanel from '../../components/HflTablePanel.vue'
import HflPagination from '../../components/HflPagination.vue'
import HflBooleanStatusTag from '../../components/HflBooleanStatusTag.vue'
import DangerConfirmDialog, { type DangerConfirmItem } from '../../components/DangerConfirmDialog.vue'
import { useProtectionSideNav } from '../../composables/useProtectionSideNav'
import { useResponsiveDrawerWidth } from '../../composables/useResponsiveDrawerWidth'
import { usePageRequestScope } from '../../composables/usePageRequestScope'
import { useListSearch } from '../../composables/useListSearch'
import { apiErrorMessage } from '../../lib/api'
import { formatLocalDateTime } from '../../lib/dateTime'
import { layoutElTable } from '../../lib/tableScrollSync'
import { listBackupConfigs, getBackupConfig, type BackupConfig, type BackupConfigDetail } from '../../lib/protectionBackupConfigApi'
import { listAllNodes } from '../../lib/nodeApi'
import { listSourceResources } from '../../lib/sourceApi'
import { listAllStorageRepositories } from '../../lib/storageRepositoryApi'
import {
  bulkDeleteBackupPolicies,
  bulkDeleteFileFilters,
  bulkSetBackupPolicyState,
  bulkSetFileFilterState,
  listBackupPolicies,
  listFileFilterRules,
  type BackupPolicy,
  type FileFilterRule,
} from '../../lib/protectionPolicyApi'
import {
  backupPolicyToForm,
  compileFilterIgnorePatterns,
  fileFilterRuleToForm,
  summarizeSchedule,
  summarizeRetention,
  summarizeFilters,
  type BackupPolicyForm,
  type FileFilterRuleForm,
  type MessageLocale,
} from '../../lib/protectionPolicyFormModel'

type PolicyRow = {
  id: string
  apiId: number
  name: string
  is_active: boolean
  storePolicyId?: string
  formData?: BackupPolicyForm
  scheduleSummary: string
  retentionSummary: string
  filterSummary: string
  createdAt: string
  relatedBackupCount: number
  updatedAt?: string
}

type FilterRow = {
  id: string
  apiId: number
  name: string
  is_active: boolean
  storeFilterId?: string
  excludeRuleLines: string[]
  formData?: FileFilterRuleForm
  createdAt: string
  relatedBackupCount: number
  updatedAt?: string
}

type PolicyRetentionDetailLine = {
  label?: string
  text: string
}

const FILTER_RULES_LIST_PREVIEW_LIMIT = 5

const { t, locale } = useI18n()
const { drawerSize } = useResponsiveDrawerWidth()
const pageRequests = usePageRequestScope()
const route = useRoute()
const router = useRouter()

const messageLocale = computed<MessageLocale>(() => 'en')

const TABLE_HEADER_STYLE: Record<string, string> = {
  background: 'rgba(248, 250, 252, 0.96)',
  color: 'rgb(71 85 105)',
  fontWeight: '600',
  whiteSpace: 'nowrap',
}

const listTab = ref<'backup' | 'filter'>('backup')

function syncListTabFromRoute() {
  const q = String(route.query.tab ?? '')
  listTab.value = q === 'filter' ? 'filter' : 'backup'
}

onMounted(() => {
  syncListTabFromRoute()
  void loadActiveList()
})

watch(
  () => route.query.tab,
  () => {
    syncListTabFromRoute()
  },
)

const pageTitleOverride = computed(() =>
  listTab.value === 'filter'
    ? t('protection.side.fileFilterRules')
    : t('protection.side.backupPolicies'),
)

const deleteConfirmRows = computed(() =>
  deleteConfirmKind.value === 'policy'
    ? deleteConfirmPolicies.value
    : deleteConfirmFilters.value,
)

const deleteConfirmTitle = computed(() =>
  deleteConfirmKind.value === 'policy'
    ? t('protection.policiesPage.deletePolicyTitle')
    : t('protection.policiesPage.deleteFilterTitle'),
)

const deleteConfirmMessage = computed(() =>
  deleteConfirmKind.value === 'policy'
    ? t('protection.policiesPage.deletePoliciesConfirm', { n: deleteConfirmPolicies.value.length })
    : t('protection.policiesPage.deleteFiltersConfirm', { n: deleteConfirmFilters.value.length }),
)

const deleteConfirmItemsHeading = computed(() =>
  deleteConfirmKind.value === 'policy'
    ? t('protection.side.backupPolicies')
    : t('protection.side.fileFilterRules'),
)

const deleteConfirmItems = computed<DangerConfirmItem[]>(() =>
  deleteConfirmRows.value.map((row) => ({
    key: row.id,
    name: row.name,
    status: {
      label: row.is_active
        ? t('protection.policiesPage.statusOn')
        : t('protection.policiesPage.statusOff'),
      tone: row.is_active ? 'success' : 'neutral',
    },
    description: deleteConfirmKind.value === 'policy'
      ? (row as PolicyRow).scheduleSummary
      : (row as FilterRow).excludeRuleLines.slice(0, 2).join(', ') || t('protection.policiesPage.colFilterSummary'),
  })),
)

const stateConfirmRows = computed(() =>
  stateConfirmKind.value === 'policy'
    ? stateConfirmPolicies.value
    : stateConfirmFilters.value,
)

const stateConfirmEntityLabel = computed(() =>
  stateConfirmKind.value === 'policy'
    ? t('protection.side.backupPolicies')
    : t('protection.side.fileFilterRules'),
)

const stateConfirmTitle = computed(() => {
  if (stateConfirmKind.value === 'policy') {
    return stateConfirmEnabled.value
      ? t('protection.policiesPage.confirmEnablePoliciesTitle')
      : t('protection.policiesPage.confirmDisablePoliciesTitle')
  }
  return stateConfirmEnabled.value
    ? t('protection.policiesPage.confirmEnableFiltersTitle')
    : t('protection.policiesPage.confirmDisableFiltersTitle')
})

const stateConfirmBaseMessage = computed(() => {
  const n = stateConfirmRows.value.length
  if (stateConfirmKind.value === 'policy') {
    return stateConfirmEnabled.value
      ? t('protection.policiesPage.confirmEnablePoliciesMessage', { n })
      : t('protection.policiesPage.confirmDisablePoliciesMessage', { n })
  }
  return stateConfirmEnabled.value
    ? t('protection.policiesPage.confirmEnableFiltersMessage', { n })
    : t('protection.policiesPage.confirmDisableFiltersMessage', { n })
})

const stateConfirmSkipNotice = computed(() => {
  const selected = stateConfirmSelectedCount.value
  const changed = stateConfirmRows.value.length
  const skipped = Math.max(0, selected - changed)
  if (!skipped) return ''
  return stateConfirmEnabled.value
    ? t('protection.policiesPage.batchEnableSkipNotice', { selected, changed, skipped })
    : t('protection.policiesPage.batchDisableSkipNotice', { selected, changed, skipped })
})

const stateConfirmMessage = computed(() =>
  stateConfirmSkipNotice.value
    ? `${stateConfirmSkipNotice.value}\n\n${stateConfirmBaseMessage.value}`
    : stateConfirmBaseMessage.value,
)

const stateConfirmWarning = computed(() => {
  if (stateConfirmKind.value === 'policy') {
    return stateConfirmEnabled.value
      ? t('protection.policiesPage.confirmEnablePoliciesWarning')
      : t('protection.policiesPage.confirmDisablePoliciesWarning')
  }
  return stateConfirmEnabled.value
    ? t('protection.policiesPage.confirmEnableFiltersWarning')
    : t('protection.policiesPage.confirmDisableFiltersWarning')
})

const stateConfirmKeyword = computed(() =>
  stateConfirmEnabled.value
    ? t('protection.policiesPage.enableKeyword')
    : t('protection.policiesPage.disableKeyword'),
)

const stateConfirmKeywordHint = computed(() =>
  stateConfirmEnabled.value
    ? t('protection.policiesPage.enableKeywordHint', { n: stateConfirmRows.value.length })
    : t('protection.policiesPage.disableKeywordHint', { n: stateConfirmRows.value.length }),
)

const stateConfirmItems = computed<DangerConfirmItem[]>(() =>
  stateConfirmRows.value.map((row) => ({
    key: row.id,
    name: row.name,
    status: {
      label: row.is_active
        ? t('protection.policiesPage.statusOn')
        : t('protection.policiesPage.statusOff'),
      tone: row.is_active ? 'success' : 'neutral',
    },
    description: stateConfirmKind.value === 'policy'
      ? (row as PolicyRow).scheduleSummary
      : (row as FilterRow).excludeRuleLines.slice(0, 2).join(', ') || t('protection.policiesPage.colFilterSummary'),
  })),
)

const listSearchPlaceholder = computed(() =>
  listTab.value === 'filter'
    ? t('protection.listSearch.fileFilter')
    : t('protection.listSearch.backupPolicy'),
)

const protectionMenus = useProtectionSideNav()

const policyRows = ref<PolicyRow[]>([])
const filterRows = ref<FilterRow[]>([])
const policyTotal = ref(0)
const filterTotal = ref(0)
const listLoading = ref(false)
const listError = ref('')
const listActionLoading = ref(false)
const searchQuery = ref('')
const searchField = ref<'name'>('name')
const {
  appliedSearch: appliedSearchQuery,
  clearSearch,
  resetSearch,
  runSearchNow: runFilterSearch,
} = useListSearch(searchQuery, () => {
  clearListSelection()
  resetToFirstPageAndLoad()
})
const pageSize = ref(30)
const currentPage = ref(1)
const policyTableRef = ref<InstanceType<typeof ElTable> | null>(null)
const filterTableRef = ref<InstanceType<typeof ElTable> | null>(null)
const selectedPolicies = ref<PolicyRow[]>([])
const selectedFilters = ref<FilterRow[]>([])
const deleteConfirmOpen = ref(false)
const deleteConfirmKind = ref<'policy' | 'filter'>('policy')
const deleteConfirmPolicies = ref<PolicyRow[]>([])
const deleteConfirmFilters = ref<FilterRow[]>([])
const stateConfirmOpen = ref(false)
const stateConfirmKind = ref<'policy' | 'filter'>('policy')
const stateConfirmEnabled = ref(true)
const stateConfirmSelectedCount = ref(0)
const stateConfirmPolicies = ref<PolicyRow[]>([])
const stateConfirmFilters = ref<FilterRow[]>([])
const moreActionsOpen = ref(false)
const detailDrawerOpen = ref(false)
const activePolicy = ref<PolicyRow | null>(null)
const policyDetailTab = ref<'basic' | 'backups'>('basic')
const filterDetailDrawerOpen = ref(false)
const filterDetailTab = ref<'basic' | 'backups'>('basic')
const activeFilter = ref<FilterRow | null>(null)
const relatedBackupConfigs = ref<BackupConfig[]>([])
const relatedBackupConfigsLoading = ref(false)
const relatedBackupConfigsError = ref('')
const filterRelatedBackupConfigs = ref<BackupConfig[]>([])
const filterRelatedBackupConfigsLoading = ref(false)
const filterRelatedBackupConfigsError = ref('')
const backupConfigDetailById = ref(new Map<number, BackupConfigDetail>())
const agentNameById = ref(new Map<number, string>())
const nasNameById = ref(new Map<number, string>())
const repositoryNameById = ref(new Map<number, string>())

function formFromPolicyApi(policy: BackupPolicy): BackupPolicyForm {
  return backupPolicyToForm(policy)
}

function policyRowFromApi(policy: BackupPolicy): PolicyRow {
  const formData = formFromPolicyApi(policy)
  return {
    id: String(policy.id),
    apiId: policy.id,
    name: policy.name,
    is_active: policy.is_active,
    formData,
    scheduleSummary: summarizeSchedule(formData, messageLocale.value),
    retentionSummary: summarizeRetention(formData, messageLocale.value),
    filterSummary: summarizeFilters(formData, messageLocale.value),
    createdAt: policy.created_at,
    updatedAt: policy.updated_at,
    relatedBackupCount: Number(policy.related_backup_count) || 0,
  }
}

function formFromFilterApi(rule: FileFilterRule): FileFilterRuleForm {
  return fileFilterRuleToForm(rule)
}

function filterExcludeRuleLinesFromForm(form: FileFilterRuleForm): string[] {
  return compileFilterIgnorePatterns(form)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
}

function filterRowFromApi(rule: FileFilterRule): FilterRow {
  const formData = formFromFilterApi(rule)
  return {
    id: String(rule.id),
    apiId: rule.id,
    name: rule.name,
    is_active: rule.is_active,
    excludeRuleLines: filterExcludeRuleLinesFromForm(formData),
    formData,
    createdAt: rule.created_at,
    updatedAt: rule.updated_at,
    relatedBackupCount: Number(rule.related_backup_count) || 0,
  }
}

let listRequestSeq = 0

async function loadActiveList(showSuccess = false) {
  const seq = ++listRequestSeq
  const tab = listTab.value
  const signal = pageRequests.nextSignal('policy-list')
  listLoading.value = true
  listError.value = ''
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      search: appliedSearchQuery.value.trim() || undefined,
      search_field: appliedSearchQuery.value.trim() ? searchField.value : undefined,
      ordering: '-created_at',
    }
    if (tab === 'backup') {
      const result = await listBackupPolicies(params, { signal })
      if (seq !== listRequestSeq) return
      policyRows.value = result.results.map(policyRowFromApi)
      policyTotal.value = result.count
      if (activePolicy.value) {
        activePolicy.value = policyRows.value.find((row) => row.id === activePolicy.value?.id) ?? activePolicy.value
      }
    } else {
      const result = await listFileFilterRules(params, { signal })
      if (seq !== listRequestSeq) return
      filterRows.value = result.results.map(filterRowFromApi)
      filterTotal.value = result.count
      if (activeFilter.value) {
        activeFilter.value = filterRows.value.find((row) => row.id === activeFilter.value?.id) ?? activeFilter.value
      }
    }
    if (showSuccess) ElMessage.success({ message: t('protection.policiesPage.msgListRefreshed'), grouping: true })
  } catch (err) {
    if (pageRequests.isAbortError(err)) return
    if (seq !== listRequestSeq) return
    listError.value = apiErrorMessage(err, t('protection.policiesPage.msgListLoadFailed'))
  } finally {
    pageRequests.releaseSignal('policy-list', signal)
    if (seq === listRequestSeq && !signal.aborted) listLoading.value = false
  }
}

function resetToFirstPageAndLoad() {
  if (currentPage.value !== 1) {
    currentPage.value = 1
    return
  }
  void loadActiveList()
}

const selectedPolicyCount = computed(() => selectedPolicies.value.length)
const selectedFilterCount = computed(() => selectedFilters.value.length)
const activeSelectedCount = computed(() => (listTab.value === 'backup' ? selectedPolicyCount.value : selectedFilterCount.value))

const filteredPolicyRows = computed(() => {
  return policyRows.value
})

const filteredFilterRows = computed(() => {
  return filterRows.value
})

const totalFiltered = computed(() =>
  listTab.value === 'backup' ? policyTotal.value : filterTotal.value,
)

const pagedPolicyRows = computed(() => {
  return filteredPolicyRows.value
})

const pagedFilterRows = computed(() => {
  return filteredFilterRows.value
})

function clearListSelection() {
  selectedPolicies.value = []
  selectedFilters.value = []
  policyTableRef.value?.clearSelection()
  filterTableRef.value?.clearSelection()
}

function layoutActiveTable() {
  requestAnimationFrame(() => {
    layoutElTable((listTab.value === 'backup' ? policyTableRef.value : filterTableRef.value) as Parameters<typeof layoutElTable>[0])
  })
}

watch(listTab, (v) => {
  resetSearch()
  searchField.value = 'name'
  currentPage.value = 1
  clearListSelection()
  const nextTab = v === 'filter' ? 'filter' : 'backup'
  if (route.query.tab !== nextTab) {
    void router.replace({ path: route.path, query: { ...route.query, tab: nextTab } })
  }
  if (currentPage.value === 1) void loadActiveList()
  layoutActiveTable()
})

watch(listLoading, (loading) => {
  if (!loading) {
    layoutActiveTable()
  }
})

watch(pageSize, () => {
  resetToFirstPageAndLoad()
})

watch(currentPage, () => {
  void loadActiveList()
})

watch(totalFiltered, (total) => {
  const maxPage = Math.max(1, Math.ceil(total / pageSize.value))
  if (currentPage.value > maxPage) currentPage.value = maxPage
})

watch(messageLocale, () => {
  policyRows.value = policyRows.value.map((row) => ({
    ...row,
    scheduleSummary: row.formData ? summarizeSchedule(row.formData, messageLocale.value) : row.scheduleSummary,
    retentionSummary: row.formData ? summarizeRetention(row.formData, messageLocale.value) : row.retentionSummary,
    filterSummary: row.formData ? summarizeFilters(row.formData, messageLocale.value) : row.filterSummary,
  }))
  filterRows.value = filterRows.value.map((row) => ({
    ...row,
    excludeRuleLines: row.formData ? filterExcludeRuleLinesFromForm(row.formData) : row.excludeRuleLines,
  }))
})

function openAddDialog() {
  void router.push({
    path: '/protection/policies/create',
    query: { kind: listTab.value === 'filter' ? 'filter' : 'backup' },
  })
}

async function refreshPoliciesList() {
  await loadActiveList(true)
}

function openPolicyDetail(row: PolicyRow) {
  activePolicy.value = row
  policyDetailTab.value = 'basic'
  detailDrawerOpen.value = true
  void loadRelatedBackupConfigs(row)
}

function onPolicyDetailClosed() {
  activePolicy.value = null
  relatedBackupConfigs.value = []
  relatedBackupConfigsError.value = ''
}

function fmtLocalTime(v: string | null | undefined) {
  return formatLocalDateTime(v, t('protection.policiesPage.timeDash'), locale.value)
}

function policyRetentionDetailLines(row: PolicyRow): PolicyRetentionDetailLine[] {
  const f = row.formData
  if (!f) return [{ text: row.retentionSummary || t('protection.policiesPage.timeDash') }]
  if (!f.sectionRetentionEnabled) return [{ text: 'Not configured' }]

  if (messageLocale.value === 'en') {
    const latestSuffix = Number(f.retentionRecentPoints) === 1 ? 'point' : 'points'
    const lines: PolicyRetentionDetailLine[] = [{ text: `Keep last ${f.retentionRecentPoints} restore ${latestSuffix}.` }]
    if (f.retentionShortHourly) {
      lines.push({ label: 'Hourly:', text: `First ${f.retentionShortDaysMax} days, one restore point per hour.` })
    }
    if (f.retentionMidDaily) {
      lines.push({ label: 'Daily:', text: `Day ${f.retentionShortDaysMax} to day ${f.retentionMidDaysMax}, one restore point per day.` })
    }
    if (f.retentionLongMonthly) {
      lines.push({ label: 'Monthly:', text: `After day ${f.retentionMidDaysMax}, one restore point per month, up to ${f.retentionLongMonths} months.` })
    }
    return lines
  }

  const lines: PolicyRetentionDetailLine[] = [{ text: `Keep the latest ${f.retentionRecentPoints} restore points.` }]
  if (f.retentionShortHourly) {
    lines.push({ label: 'Hourly:', text: `Keep one restore point per hour for the first ${f.retentionShortDaysMax} days.` })
  }
  if (f.retentionMidDaily) {
    lines.push({ label: 'Daily:', text: `Keep one restore point per day from day ${f.retentionShortDaysMax} through day ${f.retentionMidDaysMax}.` })
  }
  if (f.retentionLongMonthly) {
    lines.push({ label: 'Monthly:', text: `After day ${f.retentionMidDaysMax}, keep one restore point per month for up to ${f.retentionLongMonths} months.` })
  }
  return lines
}

function policyRetentionListSummary(row: PolicyRow): string {
  const f = row.formData
  if (!f) return row.retentionSummary || t('protection.policiesPage.timeDash')
  if (!f.sectionRetentionEnabled) return 'Not configured'
  if (messageLocale.value === 'en') {
    const suffix = Number(f.retentionRecentPoints) === 1 ? 'point' : 'points'
    return `Keep last ${f.retentionRecentPoints} restore ${suffix} ...`
  }
  return `Keep the latest ${f.retentionRecentPoints} restore points ...`
}

let relatedBackupConfigRequestSeq = 0
let filterRelatedBackupConfigRequestSeq = 0
let relatedLookupRequestSeq = 0

async function loadRelatedLookupMaps(signal?: AbortSignal) {
  const seq = ++relatedLookupRequestSeq
  try {
    const [agents, nasResources, repositories] = await Promise.all([
      listAllNodes({ role: 'agent' }, { signal }),
      listSourceResources({ resource_type: 'nas', page: 1, page_size: 500 }, { signal }).then((result) => result.results),
      listAllStorageRepositories({ page_size: 10 }, { signal }),
    ])
    if (seq !== relatedLookupRequestSeq || signal?.aborted) return
    agentNameById.value = new Map(agents.map((node) => [node.id, node.name]))
    nasNameById.value = new Map(nasResources.map((resource) => [resource.id, resource.name]))
    repositoryNameById.value = new Map(repositories.map((repo) => [repo.id, repo.name]))
  } catch {
    if (seq !== relatedLookupRequestSeq || signal?.aborted) return
  }
}

async function hydrateRelatedBackupConfigDetails(configs: BackupConfig[], signal?: AbortSignal) {
  const missing = configs.filter((config) => !backupConfigDetailById.value.has(config.id))
  if (!missing.length) return
  const details = await Promise.all(
    missing.map((config) => getBackupConfig(config.id, { signal }).catch(() => null)),
  )
  if (signal?.aborted) return
  const next = new Map(backupConfigDetailById.value)
  for (const detail of details) {
    if (detail) next.set(detail.id, detail)
  }
  backupConfigDetailById.value = next
}

async function loadRelatedBackupConfigs(policy: PolicyRow) {
  const seq = ++relatedBackupConfigRequestSeq
  const signal = pageRequests.nextSignal('policy-related-backup-configs')
  relatedBackupConfigsLoading.value = true
  relatedBackupConfigsError.value = ''
  try {
    await loadRelatedLookupMaps(signal)
    const result = await listBackupConfigs({ page: 1, page_size: 500, ordering: '-created_at' }, { signal })
    if (seq !== relatedBackupConfigRequestSeq) return
    relatedBackupConfigs.value = result.results.filter((config) => config.backup_policy_id === policy.apiId)
    await hydrateRelatedBackupConfigDetails(relatedBackupConfigs.value, signal)
  } catch (err) {
    if (pageRequests.isAbortError(err)) return
    if (seq !== relatedBackupConfigRequestSeq) return
    relatedBackupConfigsError.value = apiErrorMessage(err, t('protection.policiesPage.msgListLoadFailed'))
  } finally {
    pageRequests.releaseSignal('policy-related-backup-configs', signal)
    if (seq === relatedBackupConfigRequestSeq && !signal.aborted) relatedBackupConfigsLoading.value = false
  }
}

async function loadFilterRelatedBackupConfigs(rule: FilterRow) {
  const seq = ++filterRelatedBackupConfigRequestSeq
  const signal = pageRequests.nextSignal('filter-related-backup-configs')
  filterRelatedBackupConfigsLoading.value = true
  filterRelatedBackupConfigsError.value = ''
  try {
    await loadRelatedLookupMaps(signal)
    const result = await listBackupConfigs({ page: 1, page_size: 500, ordering: '-created_at' }, { signal })
    if (seq !== filterRelatedBackupConfigRequestSeq) return
    filterRelatedBackupConfigs.value = result.results.filter((config) => config.file_filter_rule_id === rule.apiId)
    await hydrateRelatedBackupConfigDetails(filterRelatedBackupConfigs.value, signal)
  } catch (err) {
    if (pageRequests.isAbortError(err)) return
    if (seq !== filterRelatedBackupConfigRequestSeq) return
    filterRelatedBackupConfigsError.value = apiErrorMessage(err, t('protection.policiesPage.msgListLoadFailed'))
  } finally {
    pageRequests.releaseSignal('filter-related-backup-configs', signal)
    if (seq === filterRelatedBackupConfigRequestSeq && !signal.aborted) filterRelatedBackupConfigsLoading.value = false
  }
}

function sourceTypeLabel(sourceType: string) {
  if (sourceType === 'agent') return t('protection.backupsPage.sourceTypeHost')
  if (sourceType === 'nas') return t('protection.backupsPage.sourceTypeNas')
  return sourceType || t('protection.policiesPage.timeDash')
}

function sourceRefLabel(config: BackupConfig) {
  return `${sourceTypeLabel(config.source_type)} #${config.source_ref_id}`
}

function backupConfigSourceLabel(config: BackupConfig) {
  if (config.source_type === 'agent') {
    return agentNameById.value.get(config.source_ref_id)
      ?? `${t('protection.backupsPage.sourceTypeHost')} #${config.source_ref_id}`
  }
  if (config.source_type === 'nas') {
    return nasNameById.value.get(config.source_ref_id)
      ?? `${t('protection.backupsPage.sourceTypeNas')} #${config.source_ref_id}`
  }
  return config.name || sourceRefLabel(config)
}

function repositoryLabel(repositoryId: number) {
  return repositoryNameById.value.get(repositoryId) ?? `#${repositoryId}`
}

function policyNameById(policyId: number | null | undefined) {
  if (policyId == null) return t('protection.backupsPage.flowBackupColPolicyNone')
  return policyRows.value.find((row) => row.apiId === policyId)?.name ?? `#${policyId}`
}

function filterNameById(filterId: number | null | undefined) {
  if (filterId == null) return t('protection.backupsPage.flowBackupColPolicyNone')
  return filterRows.value.find((row) => row.apiId === filterId)?.name ?? `#${filterId}`
}

function backupConfigPathsLabel(config: BackupConfig) {
  const detail = backupConfigDetailById.value.get(config.id)
  const paths = detail?.directories?.map((dir) => dir.path).filter(Boolean) ?? []
  if (paths.length) return paths.join('\n')
  if (config.directory_count > 0) {
    return t('protection.policiesPage.relatedBackupPathCount', { n: config.directory_count })
  }
  return t('protection.policiesPage.timeDash')
}

function onPolicySelectionChange(rows: PolicyRow[]) {
  selectedPolicies.value = rows
  if (!rows.length) moreActionsOpen.value = false
}

function openEditPolicy(row: PolicyRow) {
  void router.push({
    path: `/protection/policies/${row.apiId}/edit`,
    query: { kind: 'backup' },
  })
}

function editSelectedPolicy() {
  if (selectedPolicies.value.length !== 1) {
    ElMessage.warning({ message: t('protection.policiesPage.msgSelectOnePolicy'), grouping: true })
    return
  }
  openEditPolicy(selectedPolicies.value[0]!)
}

async function updateSelectedPoliciesActive(isActive: boolean) {
  const rows = selectedPolicies.value
  if (!rows.length) {
    ElMessage.warning({ message: t('protection.policiesPage.msgSelectPolicy'), grouping: true })
    return
  }
  const targets = rows.filter((row) => row.is_active !== isActive)
  if (!targets.length) {
    ElMessage.info({ message: t('protection.policiesPage.batchNoStateChange'), grouping: true })
    return
  }
  stateConfirmKind.value = 'policy'
  stateConfirmEnabled.value = isActive
  stateConfirmSelectedCount.value = rows.length
  stateConfirmPolicies.value = targets
  stateConfirmFilters.value = []
  stateConfirmOpen.value = true
}

async function executePolicyStateChange() {
  const rows = stateConfirmPolicies.value
  if (!rows.length) return
  listActionLoading.value = true
  try {
    const result = await bulkSetBackupPolicyState(
      rows.map((row) => row.apiId),
      stateConfirmEnabled.value,
    )
    await loadActiveList()
    stateConfirmOpen.value = false
    stateConfirmPolicies.value = []
    if (result.failed.length) {
      ElMessage.warning({ message: t('protection.policiesPage.msgBulkPartial', { n: result.failed.length }), grouping: true })
      return
    }
    ElMessage.success({ message: stateConfirmEnabled.value ? t('protection.policiesPage.msgPoliciesEnabled') : t('protection.policiesPage.msgPoliciesDisabled'), grouping: true })
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('protection.policiesPage.msgOperationFailed')), grouping: true })
  } finally {
    listActionLoading.value = false
  }
}

async function deleteSelectedPolicies() {
  const rows = selectedPolicies.value
  if (!rows.length) {
    ElMessage.warning({ message: t('protection.policiesPage.msgSelectPolicy'), grouping: true })
    return
  }
  deleteConfirmKind.value = 'policy'
  deleteConfirmPolicies.value = [...rows]
  deleteConfirmFilters.value = []
  deleteConfirmOpen.value = true
}

async function executeDeletePolicies() {
  const rows = deleteConfirmPolicies.value
  if (!rows.length) return
  try {
    listActionLoading.value = true
    const ids = rows.map((row) => row.apiId)
    const result = await bulkDeleteBackupPolicies(ids)
    const deletedIds = new Set(result.deleted.map(String))
    if (activePolicy.value && deletedIds.has(activePolicy.value.id)) {
      detailDrawerOpen.value = false
      activePolicy.value = null
    }
    selectedPolicies.value = []
    await loadActiveList()
    deleteConfirmOpen.value = false
    deleteConfirmPolicies.value = []
    if (result.failed.length) {
      ElMessage.warning({ message: t('protection.policiesPage.msgBulkPartial', { n: result.failed.length }), grouping: true })
      return
    }
    ElMessage.success({ message: t('protection.policiesPage.msgDeleted'), grouping: true })
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('protection.policiesPage.msgDeleteFailed')), grouping: true })
  } finally {
    listActionLoading.value = false
  }
}

function onFilterSelectionChange(rows: FilterRow[]) {
  selectedFilters.value = rows
  if (!rows.length) moreActionsOpen.value = false
}

function filterRowClassName({ row }: { row: FilterRow }) {
  return row.is_active ? '' : 'hfl-filter-row--inactive'
}

function displayedFilterExcludeRuleLines(row: FilterRow) {
  return row.excludeRuleLines.slice(0, FILTER_RULES_LIST_PREVIEW_LIMIT)
}

function hasMoreFilterExcludeRules(row: FilterRow) {
  return row.excludeRuleLines.length > FILTER_RULES_LIST_PREVIEW_LIMIT
}

function openFilterDetail(row: FilterRow) {
  activeFilter.value = row
  filterDetailTab.value = 'basic'
  filterDetailDrawerOpen.value = true
  void loadFilterRelatedBackupConfigs(row)
}

function onFilterDetailClosed() {
  activeFilter.value = null
  filterRelatedBackupConfigs.value = []
  filterRelatedBackupConfigsError.value = ''
}

function openEditFilter(row: FilterRow) {
  void router.push({
    path: `/protection/policies/${row.apiId}/edit`,
    query: { kind: 'filter' },
  })
}

function editSelectedFilter() {
  if (selectedFilters.value.length !== 1) {
    ElMessage.warning({ message: t('protection.policiesPage.msgSelectOneFilter'), grouping: true })
    return
  }
  openEditFilter(selectedFilters.value[0]!)
}

async function updateSelectedFiltersActive(isActive: boolean) {
  const rows = selectedFilters.value
  if (!rows.length) {
    ElMessage.warning({ message: t('protection.policiesPage.msgSelectFilter'), grouping: true })
    return
  }
  const targets = rows.filter((row) => row.is_active !== isActive)
  if (!targets.length) {
    ElMessage.info({ message: t('protection.policiesPage.batchNoStateChange'), grouping: true })
    return
  }
  stateConfirmKind.value = 'filter'
  stateConfirmEnabled.value = isActive
  stateConfirmSelectedCount.value = rows.length
  stateConfirmFilters.value = targets
  stateConfirmPolicies.value = []
  stateConfirmOpen.value = true
}

async function executeFilterStateChange() {
  const rows = stateConfirmFilters.value
  if (!rows.length) return
  listActionLoading.value = true
  try {
    const result = await bulkSetFileFilterState(
      rows.map((row) => row.apiId),
      stateConfirmEnabled.value,
    )
    await loadActiveList()
    stateConfirmOpen.value = false
    stateConfirmFilters.value = []
    if (result.failed.length) {
      ElMessage.warning({ message: t('protection.policiesPage.msgBulkPartial', { n: result.failed.length }), grouping: true })
      return
    }
    ElMessage.success({ message: stateConfirmEnabled.value ? t('protection.policiesPage.msgFiltersEnabled') : t('protection.policiesPage.msgFiltersDisabled'), grouping: true })
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('protection.policiesPage.msgOperationFailed')), grouping: true })
  } finally {
    listActionLoading.value = false
  }
}

async function deleteSelectedFilters() {
  const rows = selectedFilters.value
  if (!rows.length) {
    ElMessage.warning({ message: t('protection.policiesPage.msgSelectFilter'), grouping: true })
    return
  }
  deleteConfirmKind.value = 'filter'
  deleteConfirmFilters.value = [...rows]
  deleteConfirmPolicies.value = []
  deleteConfirmOpen.value = true
}

async function executeDeleteFilters() {
  const rows = deleteConfirmFilters.value
  if (!rows.length) return
  try {
    listActionLoading.value = true
    const ids = rows.map((row) => row.apiId)
    const result = await bulkDeleteFileFilters(ids)
    const deletedIds = new Set(result.deleted.map(String))
    if (activeFilter.value && deletedIds.has(activeFilter.value.id)) {
      filterDetailDrawerOpen.value = false
      activeFilter.value = null
    }
    selectedFilters.value = []
    await loadActiveList()
    deleteConfirmOpen.value = false
    deleteConfirmFilters.value = []
    if (result.failed.length) {
      ElMessage.warning({ message: t('protection.policiesPage.msgBulkPartial', { n: result.failed.length }), grouping: true })
      return
    }
    ElMessage.success({ message: t('protection.policiesPage.msgDeleted'), grouping: true })
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err, t('protection.policiesPage.msgDeleteFailed')), grouping: true })
  } finally {
    listActionLoading.value = false
  }
}

function executeDeleteConfirm() {
  if (deleteConfirmKind.value === 'policy') {
    void executeDeletePolicies()
  } else {
    void executeDeleteFilters()
  }
}

function closeDeleteConfirm() {
  if (listActionLoading.value) return
  deleteConfirmOpen.value = false
}

function executeStateConfirm() {
  if (stateConfirmKind.value === 'policy') {
    void executePolicyStateChange()
  } else {
    void executeFilterStateChange()
  }
}

function closeStateConfirm() {
  if (listActionLoading.value) return
  stateConfirmOpen.value = false
}

const moreEditDisabled = computed(() =>
  listActionLoading.value || (listTab.value === 'backup' ? selectedPolicyCount.value !== 1 : selectedFilterCount.value !== 1),
)
const moreBatchDisabled = computed(() =>
  listActionLoading.value || (listTab.value === 'backup' ? selectedPolicyCount.value === 0 : selectedFilterCount.value === 0),
)
const batchEnableDisabled = computed(() =>
  listActionLoading.value || (
    listTab.value === 'backup'
      ? !selectedPolicies.value.some((row) => !row.is_active)
      : !selectedFilters.value.some((row) => !row.is_active)
  ),
)
const batchDisableDisabled = computed(() =>
  listActionLoading.value || (
    listTab.value === 'backup'
      ? !selectedPolicies.value.some((row) => row.is_active)
      : !selectedFilters.value.some((row) => row.is_active)
  ),
)

function onMoreEdit() {
  if (listTab.value === 'backup') editSelectedPolicy()
  else editSelectedFilter()
}

async function onMoreDelete() {
  if (listTab.value === 'backup') await deleteSelectedPolicies()
  else await deleteSelectedFilters()
}

function onMoreEnable() {
  if (listTab.value === 'backup') void updateSelectedPoliciesActive(true)
  else void updateSelectedFiltersActive(true)
}

function onMoreDisable() {
  if (listTab.value === 'backup') void updateSelectedPoliciesActive(false)
  else void updateSelectedFiltersActive(false)
}

</script>

<template>
  <ModulePage
    :title="t('protection.policiesPage.pageTitle')"
    :page-title-override="pageTitleOverride"
    :menus="protectionMenus"
    body-fill
  >
    <div class="hfl-list-shell hfl-list-shell--fill">
      <HflTablePanel fill>
        <template #toolbar>
          <ElButton type="primary" @click="openAddDialog">
            <Plus :size="16" />
            {{ t('protection.policiesPage.btnCreate') }}
          </ElButton>
          <ElDropdown trigger="click" @visible-change="moreActionsOpen = $event">
            <ElButton :loading="listActionLoading">
              {{ t('protection.policiesPage.btnMoreActions') }}
              <ChevronDown
                :size="16"
                class="hfl-list-more__chev"
                :class="{ 'hfl-list-more__chev--open': moreActionsOpen }"
              />
            </ElButton>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem :disabled="moreEditDisabled" @click="onMoreEdit">
                  <span class="el-dropdown-menu__item-content">
                    <SquarePen :size="14" class="shrink-0" />
                    <span>{{ t('protection.policiesPage.btnEdit') }}</span>
                  </span>
                </ElDropdownItem>
                <ElDropdownItem divided :disabled="batchEnableDisabled" @click="onMoreEnable">
                  <span class="el-dropdown-menu__item-content">
                    <CirclePlay :size="14" class="shrink-0" />
                    <span>{{ t('protection.policiesPage.btnEnable') }}</span>
                  </span>
                </ElDropdownItem>
                <ElDropdownItem :disabled="batchDisableDisabled" @click="onMoreDisable">
                  <span class="el-dropdown-menu__item-content">
                    <CircleStop :size="14" class="shrink-0" />
                    <span>{{ t('protection.policiesPage.btnDisable') }}</span>
                  </span>
                </ElDropdownItem>
                <ElDropdownItem divided class="el-dropdown-menu__item--danger" :disabled="moreBatchDisabled" @click="onMoreDelete">
                  <span class="el-dropdown-menu__item-content">
                    <Trash2 :size="14" class="shrink-0" />
                    <span>{{ t('protection.policiesPage.btnDelete') }}</span>
                  </span>
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>

          <div class="hfl-list-toolbar__right">
            <ElInput
              v-model="searchQuery"
              clearable
              size="small"
              class="hfl-list-search hfl-list-search-group"
              :placeholder="listSearchPlaceholder"
              @search="runFilterSearch"
              @clear="clearSearch"
            >
              <template #prepend>
                <ElSelect v-model="searchField">
                  <ElOption value="name" :label="t('protection.listSearchFields.name')" />
                </ElSelect>
              </template>
              <template #prefix>
                <Search :size="16" class="hfl-list-search__icon" />
              </template>
            </ElInput>
            <ElButton
              class="hfl-refresh-button"
              :title="t('protection.policiesPage.btnRefresh')"
              :aria-label="t('protection.policiesPage.btnRefresh')"
              :disabled="listLoading"
              @click="refreshPoliciesList"
            >
              <RefreshCw :size="16" :class="{ 'is-spinning': listLoading }" />
            </ElButton>
          </div>
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
            <ElButton size="small" @click="refreshPoliciesList">
              {{ t('protection.policiesPage.btnRetry') }}
            </ElButton>
          </template>
        </ElAlert>

        <template #table="{ tableMaxHeight }">
        <el-table
          v-if="listTab === 'backup'"
          v-table-overflow-title
          v-table-header-scroll-sync
          v-table-column-resize="'protection.policies.backup'"
          ref="policyTableRef"
          v-loading="listLoading"
          class="hfl-list-table"
          :data="pagedPolicyRows"
          stripe
          row-key="id"
          :max-height="tableMaxHeight"
          :header-cell-style="TABLE_HEADER_STYLE"
          @selection-change="onPolicySelectionChange"
        >
          <el-table-column type="selection" width="35" fixed="left" />
          <el-table-column
            :label="t('protection.policiesPage.colName')"
            min-width="200"
            fixed="left"
            class-name="hfl-table-name-col"
          >
            <template #default="{ row }">
              <button
                type="button"
                class="hfl-table-name-link hfl-table-name-link--full"
                @click="openPolicyDetail(row)"
              >
                {{ row.name }}
              </button>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colAssociatedSourceCount')" width="100" align="left">
            <template #default="{ row }">
              <span class="hfl-table-cell-full hfl-table-no-tooltip">{{ row.relatedBackupCount }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colSchedule')" min-width="180">
            <template #default="{ row }">
              <span class="hfl-table-cell-full hfl-table-no-tooltip">{{ row.scheduleSummary }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colRetention')" min-width="260">
            <template #default="{ row }">
              <HflPopover
                trigger="hover"
                placement="top-start"
                :width="420"
                popper-class="policy-retention-popover"
              >
                <template #reference>
                  <span class="hfl-table-cell-full hfl-table-no-tooltip policy-retention-cell">
                    <span class="policy-retention-cell__summary">{{ policyRetentionListSummary(row) }}</span>
                  </span>
                </template>
                <div class="policy-retention-popover__content">
                  <section class="policy-retention-popover__section">
                    <div class="policy-retention-detail-list">
                      <div
                        v-for="line in policyRetentionDetailLines(row)"
                        :key="`${line.label || ''}${line.text}`"
                        class="policy-retention-detail-list__line"
                        :class="{ 'policy-retention-detail-list__line--summary': !line.label }"
                      >
                        <span v-if="line.label" class="policy-retention-detail-list__label">{{ line.label }}</span>
                        <span class="policy-retention-detail-list__text">{{ line.text }}</span>
                      </div>
                    </div>
                  </section>
                </div>
              </HflPopover>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colStatus')" width="98">
            <template #default="{ row }">
              <div class="hfl-table-no-tooltip">
                <HflBooleanStatusTag
                  :value="row.is_active"
                  :label="row.is_active ? t('protection.policiesPage.switchEnabledOn') : t('protection.policiesPage.switchEnabledOff')"
                />
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colUpdated')" width="180">
            <template #default="{ row }">
              <span class="hfl-table-cell-time">{{ fmtLocalTime(row.updatedAt) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colCreated')" width="180">
            <template #default="{ row }">
              <span class="hfl-table-cell-time">{{ fmtLocalTime(row.createdAt) }}</span>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="t('protection.policiesPage.emptyPolicies')" :image-size="72" />
          </template>
        </el-table>
        <el-table
          v-else
          v-table-overflow-title
          v-table-header-scroll-sync
          v-table-column-resize="'protection.policies.filters'"
          ref="filterTableRef"
          v-loading="listLoading"
          class="hfl-list-table"
          :data="pagedFilterRows"
          stripe
          row-key="id"
          :max-height="tableMaxHeight"
          :header-cell-style="TABLE_HEADER_STYLE"
          :row-class-name="filterRowClassName"
          @selection-change="onFilterSelectionChange"
        >
          <el-table-column type="selection" width="35" fixed="left" />
          <el-table-column
            :label="t('protection.policiesPage.colName')"
            min-width="220"
            fixed="left"
            class-name="hfl-table-name-col"
          >
            <template #default="{ row }">
              <button
                type="button"
                class="hfl-table-name-link hfl-table-name-link--full"
                @click="openFilterDetail(row)"
              >
                {{ row.name }}
              </button>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colAssociatedSourceCount')" width="100" align="left">
            <template #default="{ row }">
              <span class="hfl-table-cell-full hfl-table-no-tooltip">{{ row.relatedBackupCount }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colFilterSummary')" min-width="430">
            <template #default="{ row }">
              <HflPopover
                v-if="row.excludeRuleLines.length"
                trigger="hover"
                placement="top-start"
                :width="460"
                popper-class="hfl-filter-rules-popover"
              >
                <template #reference>
                  <div class="hfl-table-cell-full hfl-table-no-tooltip hfl-filter-rules-cell">
                    <span class="hfl-filter-rules-cell__prefix">{{ t('protection.policiesPage.filterExcludeRulesTitle') }}:</span>
                    <div class="hfl-filter-rules-cell__list">
                      <code
                        v-for="(line, index) in displayedFilterExcludeRuleLines(row)"
                        :key="`${index}-${line}`"
                        class="hfl-filter-rules-cell__rule"
                      >
                        {{ line }}
                      </code>
                      <span v-if="hasMoreFilterExcludeRules(row)" class="hfl-filter-rules-cell__more">...</span>
                    </div>
                  </div>
                </template>
                <div class="hfl-filter-rules-popover__content">
                  <div class="hfl-filter-rules-popover__divider">{{ t('protection.policiesPage.filterExcludeRulesTitle') }}</div>
                  <div class="hfl-filter-rules-popover__lines">
                    <code
                      v-for="(line, index) in row.excludeRuleLines"
                      :key="`${index}-${line}`"
                      class="hfl-filter-rules-popover__line"
                    >
                      {{ line }}
                    </code>
                  </div>
                </div>
              </HflPopover>
              <div v-else class="hfl-table-cell-full hfl-table-no-tooltip hfl-filter-rules-cell">
                <span class="hfl-filter-rules-cell__prefix">{{ t('protection.policiesPage.filterExcludeRulesTitle') }}:</span>
                <span class="hfl-filter-rules-cell__empty">
                  {{ t('protection.policiesPage.filterNoActiveRules') }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colStatus')" width="98">
            <template #default="{ row }">
              <div class="hfl-table-no-tooltip">
                <HflBooleanStatusTag
                  :value="row.is_active"
                  :label="row.is_active ? t('protection.policiesPage.switchEnabledOn') : t('protection.policiesPage.switchEnabledOff')"
                />
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colUpdated')" width="180">
            <template #default="{ row }">
              <span class="hfl-table-cell-time">{{ fmtLocalTime(row.updatedAt) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('protection.policiesPage.colCreated')" width="180">
            <template #default="{ row }">
              <span class="hfl-table-cell-time">{{ fmtLocalTime(row.createdAt) }}</span>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty :description="t('protection.policiesPage.emptyFilters')" :image-size="72" />
          </template>
        </el-table>
        </template>

        <template #footer>
          <span v-if="activeSelectedCount > 0" class="hfl-list-footer__selected">
            {{ t('protection.policiesPage.selectedCount', { n: activeSelectedCount }) }}
          </span>
          <HflPagination
            class="hfl-list-footer__pagination"
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="totalFiltered"
          />
        </template>
      </HflTablePanel>

    <ElDrawer
      v-model="detailDrawerOpen"
      direction="rtl"
      :size="drawerSize"
      destroy-on-close
      :modal="true"
      class="hfl-detail-drawer policy-detail-drawer"
      @closed="onPolicyDetailClosed"
    >
      <template #header>
        <span class="hfl-detail-drawer__title">{{ activePolicy?.name || t('protection.policiesPage.detailDrawerTitle') }}</span>
      </template>

      <div v-if="activePolicy" class="hfl-detail-drawer__body policy-detail-body">
        <ElTabs v-model="policyDetailTab" class="hfl-detail-tabs policy-detail-tabs">
          <ElTabPane :label="t('protection.sourceResources.detailTabBasic')" name="basic">
            <PolicyDetailBasicPanel
              :key="activePolicy.apiId"
              :policy-id="activePolicy.apiId"
              :created-at="activePolicy.createdAt"
              :associated-source-count="activePolicy.relatedBackupCount"
              :updated-at="activePolicy.updatedAt"
              @updated="loadActiveList"
            />
          </ElTabPane>

          <ElTabPane :label="t('protection.policiesPage.tabRelatedBackupSources')" name="backups">
            <el-alert
              v-if="relatedBackupConfigsError"
              :title="relatedBackupConfigsError"
              type="error"
              show-icon
              :closable="false"
              class="mb-3"
            />
            <el-table
              v-table-column-resize="'protection.policies.backup.related'"
              v-table-overflow-title
              v-loading="relatedBackupConfigsLoading"
              :data="relatedBackupConfigs"
              stripe
              row-key="id"
              class="hfl-list-table policy-related-backup-table"
            >
              <el-table-column :label="t('protection.backupsPage.colBackupSource')" min-width="168" fixed="left">
                <template #default="{ row }">
                  <div class="policy-related-source-cell">
                    <span class="policy-related-source-cell__name">{{ backupConfigSourceLabel(row) }}</span>
                    <span class="policy-related-source-cell__type">{{ sourceTypeLabel(row.source_type) }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column :label="t('protection.backupsPage.flowBackupColBackupName')" min-width="140">
                <template #default="{ row }">
                  <span class="font-medium text-slate-900">{{ row.name }}</span>
                </template>
              </el-table-column>
              <el-table-column :label="t('protection.backupsPage.flowBackupColBackupDirs')" min-width="180">
                <template #default="{ row }">
                  <span class="hfl-table-cell-full hfl-table-no-tooltip policy-related-paths-cell">{{ backupConfigPathsLabel(row) }}</span>
                </template>
              </el-table-column>
              <el-table-column :label="t('protection.backupsPage.flowBackupColTargetRepo')" min-width="140">
                <template #default="{ row }">{{ repositoryLabel(row.repository_id) }}</template>
              </el-table-column>
              <el-table-column :label="t('protection.backupsPage.flowBackupColBoundFileFilter')" min-width="140">
                <template #default="{ row }">{{ filterNameById(row.file_filter_rule_id) }}</template>
              </el-table-column>
              <template #empty>
                <el-empty :description="t('protection.policiesPage.emptyRelatedBackupSourcesPolicy')" :image-size="72" />
              </template>
            </el-table>
          </ElTabPane>
        </ElTabs>
      </div>
    </ElDrawer>

    <ElDrawer
      v-model="filterDetailDrawerOpen"
      direction="rtl"
      :size="drawerSize"
      destroy-on-close
      :modal="true"
      class="hfl-detail-drawer policy-detail-drawer"
      @closed="onFilterDetailClosed"
    >
      <template #header>
        <span class="hfl-detail-drawer__title">{{ activeFilter?.name || t('protection.policiesPage.filterDetailDrawerTitle') }}</span>
      </template>
      <div v-if="activeFilter" class="hfl-detail-drawer__body policy-detail-body">
        <ElTabs v-model="filterDetailTab" class="hfl-detail-tabs policy-detail-tabs">
          <ElTabPane :label="t('protection.sourceResources.detailTabBasic')" name="basic">
            <FileFilterDetailBasicPanel
              :key="activeFilter.apiId"
              :filter-id="activeFilter.apiId"
              :created-at="activeFilter.createdAt"
              :associated-source-count="activeFilter.relatedBackupCount"
              :updated-at="activeFilter.updatedAt"
              @updated="loadActiveList"
            />
          </ElTabPane>

          <ElTabPane :label="t('protection.policiesPage.tabRelatedBackupSources')" name="backups">
            <el-alert
              v-if="filterRelatedBackupConfigsError"
              :title="filterRelatedBackupConfigsError"
              type="error"
              show-icon
              :closable="false"
              class="mb-3"
            />
            <el-table
              v-table-column-resize="'protection.policies.filters.related'"
              v-table-overflow-title
              v-loading="filterRelatedBackupConfigsLoading"
              :data="filterRelatedBackupConfigs"
              stripe
              row-key="id"
              class="hfl-list-table policy-related-backup-table"
            >
              <el-table-column :label="t('protection.backupsPage.colBackupSource')" min-width="168" fixed="left">
                <template #default="{ row }">
                  <div class="policy-related-source-cell">
                    <span class="policy-related-source-cell__name">{{ backupConfigSourceLabel(row) }}</span>
                    <span class="policy-related-source-cell__type">{{ sourceTypeLabel(row.source_type) }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column :label="t('protection.backupsPage.flowBackupColBackupName')" min-width="140">
                <template #default="{ row }">
                  <span class="font-medium text-slate-900">{{ row.name }}</span>
                </template>
              </el-table-column>
              <el-table-column :label="t('protection.backupsPage.flowBackupColBackupDirs')" min-width="180">
                <template #default="{ row }">
                  <span class="hfl-table-cell-full hfl-table-no-tooltip policy-related-paths-cell">{{ backupConfigPathsLabel(row) }}</span>
                </template>
              </el-table-column>
              <el-table-column :label="t('protection.backupsPage.flowBackupColTargetRepo')" min-width="140">
                <template #default="{ row }">{{ repositoryLabel(row.repository_id) }}</template>
              </el-table-column>
              <el-table-column :label="t('protection.backupsPage.flowBackupColBoundBackupPolicy')" min-width="140">
                <template #default="{ row }">{{ policyNameById(row.backup_policy_id) }}</template>
              </el-table-column>
              <template #empty>
                <el-empty :description="t('protection.policiesPage.emptyRelatedBackupSourcesFilter')" :image-size="72" />
              </template>
            </el-table>
          </ElTabPane>
        </ElTabs>
      </div>
    </ElDrawer>
    <DangerConfirmDialog
      v-model="deleteConfirmOpen"
      :title="deleteConfirmTitle"
      :message="deleteConfirmMessage"
      :items="deleteConfirmItems"
      :items-heading="deleteConfirmItemsHeading"
      :item-name-label="t('protection.policiesPage.colName')"
      :item-status-label="t('protection.policiesPage.colStatus')"
      :item-details-label="deleteConfirmKind === 'policy'
        ? t('protection.policiesPage.colSchedule')
        : t('protection.policiesPage.colFilterSummary')"
      confirm-mode="keyword"
      :confirm-keyword="t('protection.policiesPage.deleteKeyword')"
      :confirm-keyword-hint="t('protection.policiesPage.deleteKeywordHint', { n: deleteConfirmRows.length })"
      :confirm-keyword-placeholder="t('protection.policiesPage.deleteKeyword')"
      :cancel-text="t('common.cancel')"
      :confirm-text="t('protection.policiesPage.btnDeleteConfirm')"
      :loading="listActionLoading"
      level="high"
      width="640px"
      @confirm="executeDeleteConfirm"
      @cancel="closeDeleteConfirm"
    />
    <DangerConfirmDialog
      v-model="stateConfirmOpen"
      :title="stateConfirmTitle"
      :message="stateConfirmMessage"
      :warning="stateConfirmWarning"
      :items="stateConfirmItems"
      :items-heading="stateConfirmEntityLabel"
      :item-name-label="t('protection.policiesPage.colName')"
      :item-status-label="t('protection.policiesPage.colStatus')"
      :item-details-label="stateConfirmKind === 'policy'
        ? t('protection.policiesPage.colSchedule')
        : t('protection.policiesPage.colFilterSummary')"
      confirm-mode="keyword"
      :confirm-keyword="stateConfirmKeyword"
      :confirm-keyword-hint="stateConfirmKeywordHint"
      :confirm-keyword-placeholder="stateConfirmKeyword"
      :irreversible-hint="t('protection.policiesPage.stateChangeIrreversible')"
      irreversible-tone="neutral"
      :cancel-text="t('common.cancel')"
      :confirm-text="stateConfirmEnabled
        ? t('protection.policiesPage.confirmEnableCount', { n: stateConfirmRows.length })
        : t('protection.policiesPage.confirmDisableCount', { n: stateConfirmRows.length })"
      :loading="listActionLoading"
      level="medium"
      width="640px"
      @confirm="executeStateConfirm"
      @cancel="closeStateConfirm"
    />
    </div>
  </ModulePage>
</template>

<style scoped>
.fullscreen-form-fullscreen .policy-section-nested {
  margin-top: 8px;
  padding: 18px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94) 0%, rgba(248, 250, 252, 0.92) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.78);
}

.fullscreen-form-fullscreen .policy-cron-help {
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.96) 0%, rgba(241, 245, 249, 0.92) 100%);
  border-color: var(--color-border, #e2e8f0);
}

.policy-detail-body {
  min-width: 0;
}

.policy-detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}


.policy-related-backup-table :deep(.el-table .cell) {
  line-height: 1.5;
}

.cron-row {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 8px 12px;
}

.cron-row__label {
  flex-shrink: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-regular);
  line-height: 32px;
  white-space: nowrap;
}

.cron-row__required {
  color: var(--el-color-danger);
  margin-right: 4px;
}

.cron-row__field {
  flex: 1 1 320px;
  min-width: 0;
  max-width: 460px;
}

.cron-row__error {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 20px;
  color: var(--el-color-danger);
}

.error-policy-list {
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-card);
  background: #fff;
  overflow: hidden;
}

.error-policy-list > li {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border-light, #f1f5f9);
}

.error-policy-list > li.is-last {
  border-bottom: 0;
}

.error-policy-list__switch {
  flex-shrink: 0;
  margin-top: 2px;
}

.error-policy-list__main {
  flex: 1 1 auto;
  min-width: 0;
}

.error-policy-list__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary, #0f172a);
  line-height: 1.4;
}

.error-policy-list__desc {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-secondary, #64748b);
}

.retention-tier-row {
  display: grid;
  grid-template-columns: minmax(0, 16rem) 6.5rem 140px auto;
  align-items: center;
  column-gap: 12px;
  row-gap: 6px;
}

.retention-tier-label {
  text-align: right;
  color: var(--el-text-color-regular, #606266);
}

.retention-tier-unit {
  color: var(--el-text-color-regular, #606266);
}

.retention-tier-input-wrap,
.retention-recent-input-wrap {
  width: 140px;
}

.retention-tier-input-wrap :deep(.el-input-number),
.retention-recent-input-wrap :deep(.el-input-number) {
  width: 100%;
}

@media (max-width: 560px) {
  .retention-tier-row {
    grid-template-columns: 1fr;
  }

  .retention-tier-label {
    text-align: left;
  }

  .retention-tier-input-wrap,
  .retention-recent-input-wrap {
    width: 100%;
    max-width: 200px;
  }
}

.policy-retention-cell {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  max-width: 100%;
  cursor: default;
}

.policy-retention-cell__summary {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:global(.policy-retention-popover) {
  max-width: min(420px, calc(100vw - 24px));
}

:global(.policy-retention-popover__content) {
  min-width: 0;
  padding: 2px 0;
}

:global(.policy-retention-popover__section) {
  min-width: 0;
}

:global(.policy-retention-detail-list) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:global(.policy-retention-detail-list__line) {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  align-items: start;
  column-gap: 10px;
  min-width: 0;
  color: rgb(15 23 42);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

:global(.policy-retention-detail-list__line--summary) {
  display: block;
  padding-bottom: 8px;
  border-bottom: 1px solid rgb(226 232 240);
  color: rgb(15 23 42);
  font-weight: 600;
}

:global(.policy-retention-detail-list__label) {
  color: rgb(71 85 105);
  font-weight: 600;
  white-space: nowrap;
}

:global(.policy-retention-detail-list__text) {
  min-width: 0;
  color: rgb(15 23 42);
  overflow-wrap: anywhere;
}

.hfl-filter-rules-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
  cursor: default;
}

.hfl-filter-rules-cell__prefix {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 68px;
  padding: 1px 7px;
  border: 1px solid rgb(254 215 170);
  border-radius: 999px;
  background: rgb(255 247 237);
  color: rgb(154 52 18);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.hfl-filter-rules-cell__list {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}

.hfl-filter-rules-cell__rule {
  flex: 0 1 auto;
  display: inline-block;
  max-width: 120px;
  min-width: 0;
  padding: 2px 6px;
  overflow: hidden;
  border: 1px solid rgb(226 232 240);
  border-radius: 6px;
  background: rgb(248 250 252);
  color: rgb(15 23 42);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hfl-filter-rules-cell__more {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  width: fit-content;
  padding: 0 6px;
  color: rgb(100 116 139);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.3;
}

.hfl-filter-rules-cell__empty {
  min-width: 0;
  color: rgb(100 116 139);
  font-size: 13px;
  line-height: 1.5;
}

:global(.hfl-filter-rules-popover) {
  max-width: min(460px, calc(100vw - 24px));
}

:global(.hfl-filter-rules-popover__content) {
  min-width: 0;
  padding: 2px 0;
}

:global(.hfl-filter-rules-popover__divider) {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  color: rgb(71 85 105);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
  text-transform: uppercase;
}

:global(.hfl-filter-rules-popover__divider::after) {
  content: "";
  flex: 1 1 auto;
  height: 1px;
  background: rgb(226 232 240);
}

:global(.hfl-filter-rules-popover__lines) {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  min-width: 0;
  overflow-y: auto;
}

:global(.hfl-filter-rules-popover__line) {
  display: block;
  min-width: 0;
  padding: 6px 8px;
  border: 1px solid rgb(226 232 240);
  border-radius: 6px;
  background: rgb(248 250 252);
  color: rgb(15 23 42);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

:deep(.hfl-filter-row--inactive td.el-table__cell) {
  background: rgb(248 250 252);
}

:deep(.hfl-filter-row--inactive .hfl-filter-rules-cell__rule),
:deep(.hfl-filter-row--inactive .hfl-filter-rules-cell__empty),
:deep(.hfl-filter-row--inactive .hfl-table-cell-time) {
  color: rgb(100 116 139);
}

:deep(.hfl-filter-row--inactive .hfl-filter-rules-cell__prefix) {
  opacity: 0.72;
}

.policy-related-source-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.policy-related-source-cell__name,
.policy-related-source-cell__type {
  display: block;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.policy-related-source-cell__name {
  font-weight: 500;
  color: rgb(15 23 42);
}

.policy-related-source-cell__type {
  font-size: 12px;
  color: rgb(100 116 139);
}

.policy-related-paths-cell {
  white-space: pre-line;
}

</style>
