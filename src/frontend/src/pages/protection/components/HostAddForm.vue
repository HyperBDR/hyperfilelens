<script setup lang="ts">
import { computed } from 'vue'
import NodeLifecycleWizard from '../../../components/NodeLifecycleWizard.vue'
import { getEffectiveOrgKey } from '../../../composables/useAuth'
import type { EnrollmentOs } from '../../../lib/nodeApi'

defineProps<{
  os: EnrollmentOs
}>()

const emit = defineEmits<{
  'update:os': [EnrollmentOs]
  copy: [string]
}>()

const orgKey = computed(() => getEffectiveOrgKey())
</script>

<template>
  <div class="host-add-form">
    <NodeLifecycleWizard
      install-only
      :org-key="orgKey"
      role="agent"
      :os="os"
      role-locked
      @update:os="emit('update:os', $event)"
      @copy="emit('copy', $event)"
    />
  </div>
</template>

<style scoped>
.host-add-form {
  padding: 0;
}
</style>
