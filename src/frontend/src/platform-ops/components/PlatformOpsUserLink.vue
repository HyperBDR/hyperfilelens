<script setup lang="ts">
defineProps<{
  userId?: number | string | null
  displayName?: string | null
}>()
</script>

<template>
  <router-link
    v-if="userId"
    :to="`/platform-ops/users/${userId}`"
    class="platform-user-link"
  >
    {{ displayName || userId }}
  </router-link>
  <span v-else>{{ displayName || '—' }}</span>
</template>

<style scoped>
.platform-user-link {
  color: color-mix(
    in srgb,
    var(--color-primary, #6d5ef6) 82%,
    var(--color-text-title, #1c1c26) 18%
  );
  text-decoration: none;
}

.platform-user-link:hover {
  text-decoration: underline;
}
</style>
