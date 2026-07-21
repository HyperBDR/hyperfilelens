<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  flowSourceConnectionPrimary,
  flowSourceConnectionSecondary,
  type FlowSourceConnectionRow,
} from '../../../lib/flowSourceDisplay'

const props = defineProps<{
  row: FlowSourceConnectionRow
}>()

const { t } = useI18n()

const primary = computed(() => flowSourceConnectionPrimary(props.row))

const secondary = computed(() => flowSourceConnectionSecondary(props.row))

const primaryLabel = computed(() =>
  props.row.type === 'nas'
    ? t('protection.backupsPage.connectionProxyHostnameLabel')
    : t('protection.backupsPage.connectionHostnameLabel'),
)

const secondaryLabel = computed(() =>
  props.row.type === 'nas'
    ? t('protection.backupsPage.connectionProxyIpLabel')
    : t('protection.backupsPage.connectionIpLabel'),
)
</script>

<template>
  <div class="table-stack-cell flow-source-connection-cell">
    <span class="table-stack-cell__primary">{{ primaryLabel }} {{ primary }}</span>
    <span
      v-if="secondary"
      class="table-stack-cell__secondary flow-source-connection-cell__proxy-mount"
    >
      {{ secondaryLabel }} {{ secondary }}
    </span>
  </div>
</template>
