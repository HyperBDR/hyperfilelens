<script setup lang="ts">
import { backupSourceTypeIcon, backupSourceTypeIconClass } from '../../../lib/sourceTypeIcons'
import type { FlowSourceRow } from '../composables/useFlowSourceAggregate'

defineProps<{
  row: FlowSourceRow
}>()

const emit = defineEmits<{
  open: [FlowSourceRow]
}>()
</script>

<template>
  <div class="backup-source-cell">
    <component
      :is="backupSourceTypeIcon(row.type)"
      :size="16"
      :class="backupSourceTypeIconClass(row.type)"
    />
    <button
      type="button"
      class="hfl-table-name-link hfl-table-name-link--single"
      @click.stop="emit('open', row)"
    >
      {{ row.name }}
    </button>
  </div>
</template>
