<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: number
  }>(),
  { size: 18 },
)
</script>

<template>
  <span
    class="app-logo-mark"
    :style="{ width: `${size}px`, height: `${size}px`, flex: `0 0 ${size}px` }"
    aria-hidden="true"
  />
</template>

<style scoped>
.app-logo-mark {
  position: relative;
  border: 1px solid rgba(169, 155, 255, 0.55);
  border-radius: 4px;
  background: var(--logo-core-bg, #0F0F17);
  box-shadow: 0 0 14px rgba(109, 94, 246, 0.42);
  filter: var(--logo-filter, drop-shadow(0 0 10px rgba(109, 94, 246, 0.5)));
  transform: rotate(45deg);
}

.app-logo-mark::before {
  content: '';
  position: absolute;
  inset: 4px;
  background: linear-gradient(135deg, #A99BFF, #6D5EF6);
  border-radius: 2px;
}
</style>
