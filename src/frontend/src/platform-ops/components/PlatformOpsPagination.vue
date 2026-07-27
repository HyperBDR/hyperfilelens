<script setup lang="ts">
import HflPagination from '../../components/HflPagination.vue'

defineOptions({
  name: 'PlatformOpsPagination',
  inheritAttrs: false,
})

const props = withDefaults(
  defineProps<{
    currentPage: number
    pageSize: number
    total: number
    pageSizes?: number[]
  }>(),
  {
    pageSizes: () => [20, 30, 50, 100],
  },
)

const emit = defineEmits<{
  'update:currentPage': [value: number]
  'update:pageSize': [value: number]
}>()

function updatePageSize(value: number) {
  if (props.currentPage !== 1) {
    emit('update:currentPage', 1)
  }
  emit('update:pageSize', value)
}
</script>

<template>
  <HflPagination
    v-bind="$attrs"
    class="hfl-list-footer__pagination"
    :current-page="currentPage"
    :page-size="pageSize"
    :page-sizes="pageSizes"
    :total="total"
    layout="total, sizes, prev, pager, next"
    @update:current-page="emit('update:currentPage', $event)"
    @update:page-size="updatePageSize"
  />
</template>
