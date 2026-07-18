<script setup lang="ts">
import { LoaderCircle } from 'lucide-vue-next'

defineProps<{
  label: string
  tag: 'success' | 'warning' | 'danger' | 'info' | 'neutral'
  spinning?: boolean
  neutralAsDanger?: boolean
}>()
</script>

<template>
  <div class="flow-source-status-cell hfl-table-no-tooltip">
    <el-tag
      size="small"
      :type="tag === 'neutral' && neutralAsDanger ? 'danger' : tag === 'neutral' ? undefined : tag"
      class="flow-source-status-tag"
      :class="{ 'hfl-tag--neutral': tag === 'neutral' && !neutralAsDanger }"
    >
      <LoaderCircle
        v-if="spinning"
        :size="12"
        class="flow-source-status-tag__icon"
        aria-hidden="true"
      />
      <span class="flow-source-status-tag__label">{{ label }}</span>
    </el-tag>
  </div>
</template>

<style scoped>
.flow-source-status-cell {
  display: inline-flex;
  justify-content: center;
  max-width: 100%;
  overflow: visible;
}

.flow-source-status-tag {
  max-width: none;
}

.flow-source-status-tag :deep(.el-tag__content) {
  display: inline-flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.flow-source-status-tag__icon {
  flex-shrink: 0;
  animation: flow-source-status-spin 0.8s linear infinite;
}

.flow-source-status-tag__label {
  line-height: 1.2;
}

@keyframes flow-source-status-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
