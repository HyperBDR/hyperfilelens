<script setup lang="ts">
import type { Component } from 'vue'

withDefaults(defineProps<{
  label: string
  icon?: Component | null
  iconSize?: number
  emphasis?: 'primary' | 'secondary'
}>(), {
  icon: null,
  iconSize: 13,
  emphasis: 'secondary',
})
</script>

<template>
  <span :class="['hfl-table-type-label', `hfl-table-type-label--${emphasis}`]">
    <component
      :is="icon"
      v-if="icon"
      class="hfl-table-type-label__icon"
      :size="iconSize"
      aria-hidden="true"
    />
    <span>{{ label }}</span>
  </span>
</template>
