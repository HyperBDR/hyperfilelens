<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElButton, ElDialog } from 'element-plus'
import { AlertTriangle } from 'lucide-vue-next'
import type { NodeBindings } from '../lib/nodeApi'
import './backupSourceFlowActionDialog.css'

const props = defineProps<{
  modelValue: boolean
  proxyName: string
  bindings: NodeBindings | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const { t } = useI18n()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const sourceNasRows = computed(() => props.bindings?.source_nas_resources ?? [])
const targetNasRepoRows = computed(() => props.bindings?.target_nas_repositories ?? [])
const diskRepoRows = computed(() => props.bindings?.standalone_disk_repositories ?? [])

const hasSourceNas = computed(() => sourceNasRows.value.length > 0)
const hasRepos = computed(() => targetNasRepoRows.value.length + diskRepoRows.value.length > 0)

const resourceCount = computed(() => {
  const totals = props.bindings?.totals
  if (totals) {
    return totals.source_nas_resources + totals.target_nas_repositories + totals.standalone_disk_repositories
  }
  return sourceNasRows.value.length + targetNasRepoRows.value.length + diskRepoRows.value.length
})

function close() {
  visible.value = false
}
</script>

<template>
  <ElDialog
    v-model="visible"
    :title="t('nodesPage.proxyDeleteTitle')"
    class="hfl-flow-action-dialog hfl-flow-action-dialog--confirm"
    align-center
    @close="close"
  >
    <div class="hfl-flow-action-dialog__body hfl-flow-action-dialog__body--icon-stack">
      <div class="hfl-flow-action-dialog__icon-badge hfl-flow-action-dialog__icon-badge--warning">
        <AlertTriangle :size="18" />
      </div>
      <div class="hfl-flow-action-dialog__icon-stack-content">
        <p class="hfl-flow-action-dialog__lead-text">
          {{ t('nodesPage.proxyDeleteBlockedBody', { name: proxyName, n: resourceCount }) }}
        </p>

        <div
          v-if="hasSourceNas || hasRepos"
          class="hfl-flow-action-dialog__bindings-panel"
        >
          <div
            v-if="hasSourceNas"
            class="hfl-flow-action-dialog__bindings-group"
          >
            <p class="hfl-flow-action-dialog__bindings-group-title">
              {{ t('nodesPage.proxyDeleteBlockedNasGroup', { n: sourceNasRows.length }) }}
            </p>
            <ul class="hfl-flow-action-dialog__bindings-list">
              <li
                v-for="row in sourceNasRows"
                :key="`nas-${row.id}`"
              >
                {{ row.name }}
              </li>
            </ul>
          </div>

          <div
            v-if="hasRepos"
            class="hfl-flow-action-dialog__bindings-group"
          >
            <p class="hfl-flow-action-dialog__bindings-group-title">
              {{ t('nodesPage.proxyDeleteBlockedRepoGroup', {
                n: targetNasRepoRows.length + diskRepoRows.length,
              }) }}
            </p>
            <ul class="hfl-flow-action-dialog__bindings-list">
              <li
                v-for="row in targetNasRepoRows"
                :key="`repo-nas-${row.id}`"
              >
                {{ row.name }}
              </li>
              <li
                v-for="row in diskRepoRows"
                :key="`repo-disk-${row.id}`"
              >
                {{ row.name }}
              </li>
            </ul>
          </div>
        </div>

        <p class="hfl-flow-action-dialog__hint">
          {{ t('nodesPage.proxyDeleteBlockedHint') }}
        </p>
      </div>
    </div>

    <template #footer>
      <ElButton @click="close">
        {{ t('common.close') }}
      </ElButton>
    </template>
  </ElDialog>
</template>
