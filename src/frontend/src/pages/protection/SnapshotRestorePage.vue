<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DataProtection from './DataProtection.vue'

const route = useRoute()
const snapshotId = computed(() => {
  const raw = Array.isArray(route.params.snapshotId) ? route.params.snapshotId[0] : route.params.snapshotId
  const value = Number(raw)
  return Number.isFinite(value) && value > 0 ? value : 0
})
</script>

<template>
  <DataProtection
    standalone-restore
    :fixed-restore-snapshot-id="snapshotId"
  />
</template>
