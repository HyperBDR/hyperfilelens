<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { taskStatusI18nValue, taskStatusTagAttrs } from '../lib/taskStatusDisplay'

const props = withDefaults(defineProps<{
  status?: string | null
}>(), {
  status: '',
})

const { t, te } = useI18n()
const attrs = computed(() => taskStatusTagAttrs(props.status))
const label = computed(() => {
  const value = taskStatusI18nValue(props.status)
  if (!value) return '—'
  const key = `ops.task.status.${value}`
  return te(key) ? t(key) : t('ops.task.unknownValue')
})
</script>

<template>
  <ElTag
    :type="attrs.type"
    :class="[
      attrs.class,
      'hfl-task-status-tag',
    ]"
    size="small"
  >
    {{ label }}
  </ElTag>
</template>

<style scoped>
.hfl-task-status-tag {
  box-sizing: border-box;
  max-width: 100%;
  vertical-align: middle;
}

.hfl-task-status-tag :deep(.el-tag__content) {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
