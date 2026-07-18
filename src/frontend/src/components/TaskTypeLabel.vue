<script setup lang="ts">
import { computed } from 'vue'
import { Archive, Database, Download, RotateCcw, Settings2, Trash2, Unplug } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import HflTypeLabel from './HflTypeLabel.vue'

const props = withDefaults(defineProps<{
  type?: string | null
  emphasis?: 'primary' | 'secondary'
}>(), {
  type: '',
  emphasis: 'primary',
})

const { t } = useI18n()

const typeIcons = {
  backup: Archive,
  restore: RotateCcw,
  snapshot_download: Download,
  snapshot_delete: Trash2,
  backup_config_reset: Settings2,
  source_unregister: Unplug,
  repository_operation: Database,
} as const

const icon = computed(() => {
  const type = props.type
  return type && type in typeIcons ? typeIcons[type as keyof typeof typeIcons] : null
})

const label = computed(() => {
  if (!props.type) return t('ops.task.emptyMark')
  const key = `ops.task.taskType.${props.type}`
  const translated = t(key)
  return translated === key ? props.type : translated
})
</script>

<template>
  <HflTypeLabel
    :icon="icon"
    :label="label"
    :emphasis="emphasis"
  />
</template>
