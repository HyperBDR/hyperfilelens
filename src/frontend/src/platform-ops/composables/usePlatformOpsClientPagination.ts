import { computed, ref, watch, type Ref } from 'vue'

export function usePlatformOpsClientPagination<T>(source: Ref<T[]>, defaultPageSize = 20) {
  const currentPage = ref(1)
  const pageSize = ref(defaultPageSize)
  const totalCount = computed(() => source.value.length)
  const pagedRows = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return source.value.slice(start, start + pageSize.value)
  })

  watch(pageSize, () => {
    currentPage.value = 1
  })

  watch(source, () => {
    const maxPage = Math.max(1, Math.ceil(totalCount.value / pageSize.value))
    if (currentPage.value > maxPage) {
      currentPage.value = maxPage
    }
  })

  return { currentPage, pageSize, totalCount, pagedRows }
}
