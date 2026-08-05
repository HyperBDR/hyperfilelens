<script setup lang="ts">
import { LoaderCircle } from 'lucide-vue-next'

const props = defineProps<{
  label: string
  tag: 'success' | 'warning' | 'danger' | 'info' | 'neutral'
  spinning?: boolean
  neutralAsDanger?: boolean
  clickable?: boolean
}>()

const emit = defineEmits<{
  (e: 'click', event: MouseEvent): void
}>()

function onActivate(event: MouseEvent) {
  if (!props.clickable) return
  emit('click', event)
}
</script>

<template>
  <component
    :is="clickable ? 'button' : 'div'"
    class="flow-source-status-cell hfl-table-no-tooltip"
    :class="{ 'flow-source-status-cell--clickable': clickable }"
    :type="clickable ? 'button' : undefined"
    @click="onActivate"
  >
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
  </component>
</template>

<style scoped>
.flow-source-status-cell {
  display: inline-flex;
  justify-content: center;
  max-width: 100%;
  overflow: visible;
}

.flow-source-status-cell--clickable {
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.flow-source-status-cell--clickable:focus-visible {
  outline: 2px solid rgb(37 99 235);
  outline-offset: 2px;
  border-radius: 6px;
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
