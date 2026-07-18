<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElButton, ElDialog } from 'element-plus'
import { AlertTriangle } from 'lucide-vue-next'
import { buildUpgradeConfirmSkipLines } from '../lib/nodeLifecycleUpgradeConfirm'
import type { NodeOperationBatchPreview } from '../types/nodeLifecycle'
import './backupSourceFlowActionDialog.css'

const props = defineProps<{
  modelValue: boolean
  preview: NodeOperationBatchPreview | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const { t } = useI18n()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const eligibleCount = computed(() => props.preview?.eligible.length ?? 0)

const message = computed(() =>
  t('nodeLifecycle.confirmUpgradeAgents', { n: eligibleCount.value }),
)

const skipLines = computed(() =>
  props.preview ? buildUpgradeConfirmSkipLines(t, props.preview) : [],
)

function close() {
  visible.value = false
  emit('cancel')
}

function confirm() {
  emit('confirm')
}
</script>

<template>
  <ElDialog
    v-model="visible"
    :title="t('nodeLifecycle.upgradeTitle')"
    class="hfl-flow-action-dialog hfl-flow-action-dialog--confirm"
    align-center
    @close="close"
  >
    <div class="hfl-flow-action-dialog__body hfl-flow-action-dialog__body--lead-only">
      <div class="hfl-flow-action-dialog__lead">
        <div class="hfl-flow-action-dialog__icon-badge hfl-flow-action-dialog__icon-badge--warning">
          <AlertTriangle :size="18" />
        </div>
        <div class="hfl-flow-action-dialog__icon-stack-content">
          <p class="hfl-flow-action-dialog__lead-text">
            {{ message }}
          </p>
          <p
            v-for="line in skipLines"
            :key="line"
            class="hfl-flow-action-dialog__hint"
          >
            {{ line }}
          </p>
        </div>
      </div>
    </div>

    <template #footer>
      <ElButton @click="close">
        {{ t('common.cancel') }}
      </ElButton>
      <ElButton
        type="primary"
        @click="confirm"
      >
        {{ t('nodesPage.actionUpgrade') }}
      </ElButton>
    </template>
  </ElDialog>
</template>
