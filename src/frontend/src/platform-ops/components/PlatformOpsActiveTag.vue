<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import HflBooleanStatusTag from '../../components/HflBooleanStatusTag.vue'

const props = defineProps<{ active?: boolean | null }>()
const { t } = useI18n()
const isActive = computed(() => Boolean(props.active))
</script>

<template>
  <HflBooleanStatusTag
    :value="isActive"
    :label="isActive ? t('platformOps.users.active') : t('platformOps.users.inactive')"
  />
</template>
