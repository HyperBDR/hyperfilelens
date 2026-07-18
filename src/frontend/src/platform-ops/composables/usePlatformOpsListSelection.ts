import { computed, ref } from 'vue'

export function usePlatformOpsListSelection<T>() {
  const selected = ref<T[]>([]) as { value: T[] }

  const editDisabled = computed(() => selected.value.length !== 1)
  const deleteDisabled = computed(() => selected.value.length === 0)

  function onSelectionChange(rows: T[]) {
    selected.value = rows
  }

  function clearSelection() {
    selected.value = []
  }

  return {
    selected,
    editDisabled,
    deleteDisabled,
    onSelectionChange,
    clearSelection,
  }
}
