<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import CopilotMarkdown from './CopilotMarkdown.vue'

const props = defineProps<{
  content: string
  streaming?: boolean
}>()

const displayContent = ref(props.content)
let flushTimer: ReturnType<typeof setTimeout> | null = null

function scheduleFlush(value: string) {
  if (flushTimer) clearTimeout(flushTimer)
  flushTimer = setTimeout(() => {
    displayContent.value = value
    flushTimer = null
  }, 64)
}

watch(
  () => props.content,
  (value) => {
    if (!props.streaming) {
      if (flushTimer) {
        clearTimeout(flushTimer)
        flushTimer = null
      }
      displayContent.value = value
      return
    }
    scheduleFlush(value)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (flushTimer) clearTimeout(flushTimer)
})
</script>

<template>
  <CopilotMarkdown :content="displayContent" />
</template>
