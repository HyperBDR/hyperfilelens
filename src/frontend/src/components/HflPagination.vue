<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElPagination } from 'element-plus'

defineOptions({
  name: 'HflPagination',
  inheritAttrs: false,
})

const props = withDefaults(
  defineProps<{
    currentPage?: number
    pageSize?: number
    total?: number
    pageSizes?: number[]
    layout?: string
    size?: 'large' | 'default' | 'small'
    popperClass?: string
    pagerCount?: number
  }>(),
  {
    pageSizes: () => [10, 30, 50, 100],
    layout: 'total, sizes, prev, pager, next, jumper',
    size: 'small',
    popperClass: '',
    pagerCount: 7,
  },
)

const emit = defineEmits<{
  'update:currentPage': [value: number]
  'update:pageSize': [value: number]
}>()

const mergedPopperClass = computed(() =>
  ['hfl-pagination-size-popper', props.popperClass].filter(Boolean).join(' '),
)

const paginationRef = ref<{ $el?: HTMLElement } | null>(null)

function applyInputLabels() {
  const root = paginationRef.value?.$el
  root?.querySelector<HTMLInputElement>('.el-pagination__sizes input')?.setAttribute(
    'aria-label',
    'Rows per page',
  )
  root?.querySelector<HTMLInputElement>('.el-pagination__jump input')?.setAttribute(
    'aria-label',
    'Page',
  )
}

onMounted(() => void nextTick(applyInputLabels))
watch(() => [props.currentPage, props.pageSize, props.total], () => void nextTick(applyInputLabels))
</script>

<template>
  <ElPagination
    ref="paginationRef"
    v-bind="$attrs"
    class="hfl-pagination"
    :current-page="currentPage"
    :page-size="pageSize"
    :total="total"
    :page-sizes="pageSizes"
    :layout="layout"
    :size="size"
    :popper-class="mergedPopperClass"
    :pager-count="pagerCount"
    @update:current-page="emit('update:currentPage', $event)"
    @update:page-size="emit('update:pageSize', $event)"
  />
</template>
