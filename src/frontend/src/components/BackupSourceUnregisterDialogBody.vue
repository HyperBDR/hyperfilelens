<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElCheckbox, ElTable, ElTableColumn, ElTag } from 'element-plus'
import AgentPlatformBrandIcon from './agent-deploy/AgentPlatformBrandIcon.vue'
import ExactKeywordConfirmInput from './ExactKeywordConfirmInput.vue'
import {
  buildUnregisterImpactItems,
  unregisterReasonLabel,
  type BackupSourceUnregisterDisplayRow,
} from '../lib/backupSourceUnregisterDialog'
import type { BackupSourceDeletePreflight, BackupSourceDeleteReason } from '../lib/sourceApi'
import { nasMountProtocolIcon } from '../lib/resourceIcons'
import { backupSourceTypeIcon, backupSourceTypeIconClass, type BackupSourceType } from '../lib/sourceTypeIcons'
import type { EnrollmentOs } from '../lib/nodeApi'
import './backupSourceFlowActionDialog.css'

const props = withDefaults(defineProps<{
  sourceIds: string[]
  sources?: BackupSourceUnregisterDisplayRow[]
  showSnapshots?: boolean
  isStep3?: boolean
  preflight: BackupSourceDeletePreflight | null
  displayRisks?: BackupSourceDeleteReason[]
  preflightLoading?: boolean
  loading?: boolean
  showForceOption?: boolean
}>(), {
  showSnapshots: true,
  isStep3: false,
  preflightLoading: false,
  loading: false,
  showForceOption: false,
})

const force = defineModel<boolean>('force', { default: false })
const confirmText = defineModel<string>('confirmText', { default: '' })

const emit = defineEmits<{
  (e: 'confirm'): void
}>()

const { t } = useI18n()

const hasAgentSources = computed(() => props.sourceIds.some((id) => id.startsWith('agent:')))
const hasNasSources = computed(() => props.sourceIds.some((id) => id.startsWith('nas:')))

const deleteSourceCountLabel = computed(() =>
  props.sourceIds.length === 1
    ? t('protection.backupsPage.deleteSelectedSourceSingular', { n: props.sourceIds.length })
    : t('protection.backupsPage.deleteSelectedSourcePlural', { n: props.sourceIds.length }),
)

const impactItems = computed(() =>
  buildUnregisterImpactItems(t, {
    hasAgent: hasAgentSources.value,
    hasNas: hasNasSources.value,
    isStep3: props.isStep3,
  }),
)

const displaySources = computed<BackupSourceUnregisterDisplayRow[]>(() => {
  const sourceById = new Map((props.sources || []).map((row) => [row.id, row]))
  return props.sourceIds.map((id) => {
    const source = sourceById.get(id)
    if (source) return source
    return {
      id,
      name: id,
      type: id.startsWith('agent:') ? 'Host' : id.startsWith('nas:') ? 'NAS' : '',
      statusLabel: '—',
      statusTag: 'info',
      registeredAt: '—',
      snapshotCount: '—',
    }
  })
})

function sourceTypeKind(row: BackupSourceUnregisterDisplayRow): BackupSourceType {
  if (row.sourceType) return row.sourceType
  return row.id.startsWith('nas:') ? 'nas' : 'host'
}

function sourceTypeText(row: BackupSourceUnregisterDisplayRow) {
  if (row.type) return row.type
  return sourceTypeKind(row) === 'host'
    ? t('protection.backupsPage.sourceTypeHost')
    : t('protection.backupsPage.sourceTypeNas')
}

const displayRisks = computed(() => {
  if (props.displayRisks?.length) return props.displayRisks
  return props.preflight?.risks || []
})

function reasonLabel(reason: Parameters<typeof unregisterReasonLabel>[0]) {
  return unregisterReasonLabel(reason, t)
}
</script>

<template>
  <div class="hfl-flow-action-dialog__body">
    <div
      class="hfl-flow-action-dialog__summary"
      role="region"
    >
      <ul class="hfl-flow-action-dialog__summary-list">
        <li class="hfl-flow-action-dialog__summary-list-lead">
          {{ t('protection.backupsPage.msgDeleteSourceLead', { sources: deleteSourceCountLabel }) }}
        </li>
        <li
          v-for="item in impactItems"
          :key="item"
        >
          {{ item }}
        </li>
      </ul>
    </div>

    <div class="hfl-flow-action-dialog__extras">
      <section class="hfl-flow-action-dialog__section">
        <h3 class="hfl-flow-action-dialog__section-title hfl-flow-action-dialog__section-title--plain">
          {{ t('protection.backupsPage.deleteSourceListTitle') }}
        </h3>
        <ElTable
          v-table-overflow-title
          :data="displaySources"
          size="small"
          class="hfl-flow-action-dialog__table hfl-table"
          max-height="260"
        >
          <ElTableColumn
            :label="t('protection.backupsPage.colBackupSource')"
            min-width="210"
          >
            <template #default="{ row }">
              <div class="hfl-flow-action-dialog__source-cell">
                <span class="hfl-flow-action-dialog__source-name">{{ row.name }}</span>
                <span class="hfl-flow-action-dialog__source-meta-row">
                  <span
                    class="backup-source-type-tag"
                    :class="`backup-source-type-tag--${sourceTypeKind(row)}`"
                  >
                    <component
                      :is="backupSourceTypeIcon(sourceTypeKind(row))"
                      :size="12"
                      :class="backupSourceTypeIconClass(sourceTypeKind(row))"
                    />
                    <span>{{ sourceTypeText(row) }}</span>
                  </span>
                  <span
                    v-if="sourceTypeKind(row) === 'host' && row.platform"
                    class="source-os-cell__icon-wrap hfl-flow-action-dialog__source-trait"
                  >
                    <AgentPlatformBrandIcon :os="row.platform as EnrollmentOs" />
                  </span>
                  <span
                    v-else-if="sourceTypeKind(row) === 'nas' && row.protocol"
                    class="repo-protocol-pill repo-protocol-pill--icon-only hfl-flow-action-dialog__source-trait"
                    :class="`repo-protocol-pill--${row.protocol}`"
                  >
                    <component
                      :is="nasMountProtocolIcon(row.protocol)"
                      :size="12"
                      stroke-width="2.25"
                    />
                  </span>
                </span>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn
            :label="t('protection.backupsPage.colStatus')"
            width="120"
          >
            <template #default="{ row }">
              <ElTag
                size="small"
                effect="light"
                :type="row.statusTag === 'neutral' ? undefined : (row.statusTag || 'info')"
                :class="{ 'hfl-tag--neutral': row.statusTag === 'neutral' }"
              >
                {{ row.statusLabel || '—' }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn
            v-if="showSnapshots"
            :label="t('protection.backupsPage.flowSourceDetailColSnapshotCount')"
            width="112"
            align="right"
          >
            <template #default="{ row }">
              <span class="hfl-flow-action-dialog__count tabular-nums">
                {{ row.snapshotCount ?? '—' }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn
            :label="t('protection.backupsPage.colRegistered')"
            width="150"
          >
            <template #default="{ row }">
              <span class="hfl-table-cell-time">
                {{ row.registeredAt || '—' }}
              </span>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>

      <div
        v-if="preflight?.blocking?.length"
        class="hfl-flow-action-dialog__risks"
      >
        <p class="hfl-flow-action-dialog__risks-title">
          {{ t('protection.backupsPage.deleteBlockingTitle') }}
        </p>
        <ul>
          <li
            v-for="(row, idx) in preflight.blocking"
            :key="`b-${idx}`"
          >
            {{ reasonLabel(row) }}
          </li>
        </ul>
        <p class="hfl-flow-action-dialog__risks-hint">
          {{ t('protection.backupsPage.deleteBlockingHint') }}
        </p>
      </div>

      <div
        v-if="displayRisks.length"
        class="hfl-flow-action-dialog__risks"
      >
        <p class="hfl-flow-action-dialog__risks-title">
          {{ t('protection.backupsPage.deleteStrictRiskTitle') }}
        </p>
        <ul>
          <li
            v-for="(row, idx) in displayRisks"
            :key="`r-${idx}`"
          >
            {{ reasonLabel(row) }}
          </li>
        </ul>
      </div>

      <div
        v-if="showForceOption"
        class="hfl-flow-action-dialog__force-panel"
      >
        <label class="hfl-flow-action-dialog__force">
          <ElCheckbox
            v-model="force"
            :disabled="loading || preflightLoading"
          />
          <span class="hfl-flow-action-dialog__force-copy">
            <span class="hfl-flow-action-dialog__force-label">{{ t('protection.backupsPage.deleteForceLabel') }}</span>
            <span class="hfl-flow-action-dialog__force-hint">{{ t('protection.backupsPage.deleteForceHint') }}</span>
          </span>
        </label>
      </div>

      <ExactKeywordConfirmInput
        v-model="confirmText"
        class="hfl-flow-action-dialog__confirm"
        keyword="UNREGISTER"
        :hint="t('protection.backupsPage.deleteConfirmTypeKeyword')"
        :placeholder="t('protection.backupsPage.deleteConfirmPlaceholder')"
        :disabled="loading"
        @confirm="emit('confirm')"
      />
    </div>
  </div>
</template>
