<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElButton, ElDialog } from 'element-plus'
import BackupSourceUnregisterDialogBody from './BackupSourceUnregisterDialogBody.vue'
import {
  mergeUnregisterSubmitRisks,
  unregisterReasonLabel,
  type BackupSourceUnregisterDisplayRow,
} from '../lib/backupSourceUnregisterDialog'
import {
  bulkDeleteBackupSources,
  parseBackupSourceDeleteError,
  preflightDeleteBackupSources,
  type BackupSourceDeletePreflight,
  type BackupSourceDeleteReason,
  type BackupSourceDeleteResult,
} from '../lib/sourceApi'
import './backupSourceFlowActionDialog.css'

const props = defineProps<{
  modelValue: boolean
  sourceIds: string[]
  sources?: BackupSourceUnregisterDisplayRow[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'started', payload: { sourceIds: string[] }): void
  (e: 'failed', payload: { sourceIds: string[] }): void
  (e: 'deleted', payload: {
    result: string
    warnings: Array<Record<string, unknown>>
    pending_removals: BackupSourceDeleteResult['pending_removals']
    task_id?: number
    task_uuid?: string
    task_ids?: number[]
    task_uuids?: string[]
    tasks?: BackupSourceDeleteResult['tasks']
    accepted?: boolean
  }): void
}>()

const { t } = useI18n()
const force = ref(false)
const loading = ref(false)
const preflightLoading = ref(false)
const preflight = ref<BackupSourceDeletePreflight | null>(null)
const preflightError = ref(false)
const submitErrorReasons = ref<BackupSourceDeleteReason[]>([])
const confirmText = ref('')
const frozenSourceIds = ref<string[]>([])
const frozenSources = ref<BackupSourceUnregisterDisplayRow[]>([])
let preflightRequestSeq = 0
const confirmationKeyword = computed(() => force.value ? 'FORCE UNREGISTER' : 'UNREGISTER')

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})
const dialogSourceIds = computed(() => frozenSourceIds.value)
const dialogSources = computed(() => frozenSources.value)

const title = computed(() =>
  dialogSourceIds.value.length > 1
    ? t('protection.backupsPage.titleDeleteStep3Source')
    : t('protection.backupsPage.titleDeleteStep3SourceSingle'),
)

const displayRisks = computed(() => mergeUnregisterSubmitRisks(preflight.value, submitErrorReasons.value))

const deleteDisabled = computed(() => {
  if (loading.value || preflightLoading.value) return true
  if (preflightError.value || !preflight.value) return true
  if (preflight.value?.delete_disabled) return true
  if (confirmText.value !== confirmationKeyword.value) return true
  return false
})

async function loadPreflight() {
  const requestSeq = ++preflightRequestSeq
  const sourceIds = [...dialogSourceIds.value]
  if (!sourceIds.length) {
    preflight.value = null
    preflightError.value = false
    preflightLoading.value = false
    return
  }
  preflight.value = null
  preflightError.value = false
  preflightLoading.value = true
  try {
    const result = await preflightDeleteBackupSources(sourceIds)
    if (requestSeq !== preflightRequestSeq) return
    preflight.value = result
    submitErrorReasons.value = []
  } catch {
    if (requestSeq !== preflightRequestSeq) return
    preflight.value = null
    preflightError.value = true
  } finally {
    if (requestSeq === preflightRequestSeq) preflightLoading.value = false
  }
}

function resetDialogState() {
  preflightRequestSeq += 1
  force.value = false
  confirmText.value = ''
  preflight.value = null
  preflightError.value = false
  preflightLoading.value = false
  submitErrorReasons.value = []
}

watch(
  () => [props.modelValue, props.sourceIds.join(',')] as const,
  ([open]) => {
    if (!open) {
      resetDialogState()
      return
    }
    if (loading.value) return
    frozenSourceIds.value = [...props.sourceIds]
    frozenSources.value = (props.sources || []).map(source => ({ ...source }))
    resetDialogState()
    void loadPreflight()
  },
  { immediate: true },
)

watch(force, () => {
  confirmText.value = ''
})

function close() {
  if (loading.value) return
  visible.value = false
}

async function confirmDelete() {
  if (deleteDisabled.value || !dialogSourceIds.value.length) return
  const sourceIds = [...dialogSourceIds.value]
  const forceDelete = force.value
  const confirmation = confirmText.value
  emit('started', { sourceIds })
  loading.value = true
  try {
    const result = await bulkDeleteBackupSources(sourceIds, forceDelete, confirmation)
    submitErrorReasons.value = []
    visible.value = false
    emit('deleted', {
      result: result.result,
      warnings: result.warnings || [],
      pending_removals: result.pending_removals || [],
      task_id: result.task_id,
      task_uuid: result.task_uuid,
      task_ids: result.task_ids,
      task_uuids: result.task_uuids,
      tasks: result.tasks,
      accepted: Boolean(result.accepted),
    })
  } catch (err: unknown) {
    const parsed = parseBackupSourceDeleteError(err)
    submitErrorReasons.value = parsed.reasons
    emit('failed', { sourceIds })
    const lines = parsed.reasons.length
      ? parsed.reasons.map((reason) => unregisterReasonLabel(reason, t)).join('\n')
      : parsed.message || t('protection.backupsPage.msgDeleteSourceFailed')
    const { ElMessage } = await import('element-plus')
    ElMessage.error({
      message: lines,
      duration: 8000,
      showClose: true,
      grouping: true,
    })
    void loadPreflight()
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <ElDialog
    v-model="visible"
    :title="title"
    class="hfl-flow-action-dialog hfl-flow-action-dialog--delete"
    align-center
    :close-on-click-modal="!loading"
    :close-on-press-escape="!loading"
    @close="close"
  >
    <BackupSourceUnregisterDialogBody
      v-model:force="force"
      v-model:confirm-text="confirmText"
      :source-ids="dialogSourceIds"
      :sources="dialogSources"
      :show-snapshots="true"
      is-step3
      :preflight="preflight"
      :display-risks="displayRisks"
      :preflight-loading="preflightLoading"
      :preflight-error="preflightError"
      :loading="loading"
      @retry-preflight="loadPreflight"
      @confirm="confirmDelete"
    />

    <template #footer>
      <ElButton
        :disabled="loading"
        @click="close"
      >
        {{ t('common.cancel') }}
      </ElButton>
      <ElButton
        type="danger"
        :loading="loading"
        :disabled="deleteDisabled"
        @click="confirmDelete"
      >
        {{ t('protection.backupsPage.btnConfirmUnregisterSource') }}
      </ElButton>
    </template>
  </ElDialog>
</template>
