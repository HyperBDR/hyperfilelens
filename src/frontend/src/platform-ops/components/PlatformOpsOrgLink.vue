<script setup lang="ts">
defineProps<{
  orgId?: number | string | null
  orgKey?: string | null
  /** Visible link text; falls back to orgKey or orgId. */
  label?: string | null
}>()
</script>

<template>
  <router-link
    v-if="orgId"
    :to="`/platform-ops/orgs/${orgId}`"
    class="platform-org-link"
  >
    {{ label || orgKey || orgId }}
  </router-link>
  <span v-else>{{ label || orgKey || '—' }}</span>
</template>

<style scoped>
.platform-org-link {
  color: var(--color-primary);
  text-decoration: none;
}

.platform-org-link:hover {
  text-decoration: underline;
}
</style>
