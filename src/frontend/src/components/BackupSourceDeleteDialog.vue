<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElButton, ElDialog } from 'element-plus'
import BackupSourceUnregisterDialogBody from './BackupSourceUnregisterDialogBody.vue'
import {
  mergeUnregisterSubmitRisks,
  shouldOfferForceUnregister,
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
  showSnapshots?: boolean
  retryAfterFailure?: boolean
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
    accepted?: boolean
  }): void
}>()

const { t } = useI18n()
const force = ref(false)
const loading = ref(false)
const preflightLoading = ref(false)
const preflight = ref<BackupSourceDeletePreflight | null>(null)
const submitErrorReasons = ref<BackupSourceDeleteReason[]>([])
const submitFailed = ref(false)
const confirmText = ref('')

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const title = computed(() =>
  props.sourceIds.length > 1
    ? t('protection.backupsPage.titleDeleteSource')
    : t('protection.backupsPage.titleDeleteSourceSingle'),
)

const displayRisks = computed(() => mergeUnregisterSubmitRisks(preflight.value, submitErrorReasons.value))

const showForceOption = computed(() =>
  shouldOfferForceUnregister({
    preflight: preflight.value,
    submitErrorReasons: submitErrorReasons.value,
    retryAfterFailure: props.retryAfterFailure,
    submitFailed: submitFailed.value,
  }),
)

const strictMayFail = computed(() =>
  Boolean(preflight.value?.strict_may_fail || submitErrorReasons.value.length),
)

const deleteDisabled = computed(() => {
  if (loading.value || preflightLoading.value) return true
  if (preflight.value?.delete_disabled) return true
  if (showForceOption.value && strictMayFail.value && !force.value) return true
  if (confirmText.value !== 'UNREGISTER') return true
  return false
})

async function loadPreflight() {
  if (!props.sourceIds.length) {
    preflight.value = null
    return
  }
  preflightLoading.value = true
  try {
    preflight.value = await preflightDeleteBackupSources(props.sourceIds)
  } catch {
    preflight.value = { risks: [], blocking: [], strict_may_fail: false, delete_disabled: false }
  } finally {
    preflightLoading.value = false
  }
}

watch(
  () => [props.modelValue, props.sourceIds.join(','), props.retryAfterFailure] as const,
  ([open]) => {
    if (!open) {
      force.value = false
      confirmText.value = ''
      preflight.value = null
      submitErrorReasons.value = []
      submitFailed.value = false
      return
    }
    confirmText.value = ''
    submitErrorReasons.value = []
    submitFailed.value = false
    force.value = props.retryAfterFailure
    void loadPreflight()
  },
)

function close() {
  if (loading.value) return
  visible.value = false
}

async function confirmDelete() {
  if (deleteDisabled.value || !props.sourceIds.length) return
  const sourceIds = [...props.sourceIds]
  const forceDelete = showForceOption.value ? force.value : false
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
      accepted: Boolean(result.accepted),
    })
  } catch (err: unknown) {
    const parsed = parseBackupSourceDeleteError(err)
    submitErrorReasons.value = parsed.reasons
    submitFailed.value = true
    if (shouldOfferForceUnregister({ submitErrorReasons: parsed.reasons, retryAfterFailure: true })) {
      force.value = true
    }
    emit('failed', { sourceIds })
    const reasonLines = parsed.reasons.length
      ? parsed.reasons.map((reason) => unregisterReasonLabel(reason, t)).join('\n')
      : parsed.message || t('protection.backupsPage.msgDeleteSourceFailed')
    const message = parsed.hint ? `${reasonLines}\n\n${parsed.hint}` : reasonLines
    const { ElMessage } = await import('element-plus')
    ElMessage.error({
      message,
      duration: 10000,
      showClose: true,
      grouping: true,
    })
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
      :source-ids="sourceIds"
      :sources="sources"
      :show-snapshots="showSnapshots === true"
      :preflight="preflight"
      :display-risks="displayRisks"
      :preflight-loading="preflightLoading"
      :loading="loading"
      :show-force-option="showForceOption"
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
