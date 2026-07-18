<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { backupSourceTypeIcon, backupSourceTypeIconClass } from '../../../lib/sourceTypeIcons'
import { flowSourceKindLabel } from '../../../lib/flowSourceDisplay'
import type { FlowSourceRow } from '../composables/useFlowSourceAggregate'

const props = defineProps<{
  row: FlowSourceRow
  interactive?: boolean
  externallyInteractive?: boolean
}>()

const emit = defineEmits<{
  open: [FlowSourceRow]
}>()

const { t } = useI18n()
const interactive = computed(() => props.interactive !== false)
const clickableAppearance = computed(() => interactive.value || props.externallyInteractive === true)

function onClick(event: MouseEvent) {
  if (!interactive.value) return
  event.stopPropagation()
  emit('open', props.row)
}

const sourceTypeLabel = computed(() =>
  flowSourceKindLabel(props.row, {
    host: t('protection.backupsPage.sourceTypeHost'),
    nas: t('protection.backupsPage.sourceTypeNas'),
  }),
)
const sourceTraitLabel = computed(() => {
  if (props.row.type === 'host') {
    const keys: Record<string, string> = {
      windows: 'protection.sourceResources.osPlatformWindows',
      macos: 'protection.sourceResources.osPlatformMacos',
      linux: 'protection.sourceResources.osPlatformLinux',
    }
    const key = keys[String(props.row.platform || '')]
    return key ? t(key) : ''
  }
  if (props.row.protocol === 'smb') return t('repositoriesPage.protocolSmb')
  if (props.row.protocol === 'nfs') return t('repositoriesPage.protocolNfs')
  return ''
})
</script>

<template>
  <component
    :is="interactive ? 'button' : 'div'"
    :type="interactive ? 'button' : undefined"
    class="backup-source-cell backup-source-cell--summary backup-source-cell--stacked-summary"
    :class="{ 'backup-source-cell--clickable': clickableAppearance }"
    @click="onClick"
  >
    <span class="backup-source-cell__body">
      <span
        class="hfl-table-name-link--single"
        :class="clickableAppearance ? 'hfl-table-name-link' : 'backup-source-cell__name'"
      >
        {{ row.name }}
      </span>
      <span class="backup-source-cell__meta-row">
        <span
          class="backup-source-type-tag"
          :class="`backup-source-type-tag--${row.type}`"
        >
          <component
            :is="backupSourceTypeIcon(row.type)"
            :size="12"
            :class="backupSourceTypeIconClass(row.type)"
          />
          <span>
            {{ sourceTypeLabel }}<template v-if="sourceTraitLabel"> · {{ sourceTraitLabel }}</template>
          </span>
        </span>
      </span>
    </span>
  </component>
</template>
