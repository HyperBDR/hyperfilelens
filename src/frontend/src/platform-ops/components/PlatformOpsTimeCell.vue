<script setup lang="ts">
import { formatLocalDateTime } from '../../lib/dateTime'

defineProps<{ value?: string | null }>()
</script>

<template>
  <span class="hfl-table-cell-time">{{ formatLocalDateTime(value, '—') }}</span>
</template>
