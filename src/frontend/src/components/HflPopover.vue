<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElPopover } from 'element-plus'
import { useResponsiveLayout } from '../composables/useResponsiveLayout'

const HOVER_POPOVER_SHOW_AFTER_MS = 300

const props = defineProps<{
  trigger?: string
  showAfter?: number
}>()

const popoverRef = ref<InstanceType<typeof ElPopover> | null>(null)
const { isTouchLike } = useResponsiveLayout()

const resolvedTrigger = computed(() => {
  const requestedTrigger = props.trigger ?? 'hover'
  return requestedTrigger === 'hover' && isTouchLike.value ? 'click' : requestedTrigger
})
const resolvedShowAfter = computed(() => props.showAfter ?? (resolvedTrigger.value === 'hover' ? HOVER_POPOVER_SHOW_AFTER_MS : 0))

function hide() {
  popoverRef.value?.hide?.()
}

defineExpose({ hide })
</script>

<template>
  <ElPopover
    ref="popoverRef"
    v-bind="$attrs"
    :trigger="resolvedTrigger"
    :show-after="resolvedShowAfter"
  >
    <template
      v-for="(_, name) in $slots"
      #[name]="slotProps"
    >
      <slot
        :name="name"
        v-bind="slotProps ?? {}"
      />
    </template>
  </ElPopover>
</template>
