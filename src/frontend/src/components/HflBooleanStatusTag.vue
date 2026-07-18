<script setup lang="ts">
import { computed } from 'vue'
import { booleanStatusTag } from '../lib/statusTag'

const props = withDefaults(defineProps<{
  value?: boolean | null
  label: string
  size?: 'large' | 'default' | 'small'
  effect?: 'dark' | 'light' | 'plain'
}>(), {
  value: false,
  size: 'small',
  effect: 'light',
})

const tagAttrs = computed(() => booleanStatusTag(Boolean(props.value)))
</script>

<template>
  <ElTag
    :type="tagAttrs.type"
    :class="tagAttrs.class"
    :size="size"
    :effect="effect"
  >
    {{ label }}
  </ElTag>
</template>
