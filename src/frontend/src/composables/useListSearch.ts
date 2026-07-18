import { ref, watch, type Ref } from 'vue'
import { useDebouncedAction } from './useDebouncedAction'

export function useListSearch(
  input: Ref<string>,
  onApply: () => void = () => undefined,
  delay = 900,
) {
  const appliedSearch = ref(input.value)
  const skipNextInputWatch = ref(false)

  function applyCurrentSearch() {
    appliedSearch.value = input.value
    onApply()
  }

  const {
    schedule: scheduleSearch,
    runNow: runSearchNow,
    cancel: cancelSearch,
  } = useDebouncedAction(applyCurrentSearch, delay)

  watch(input, () => {
    if (skipNextInputWatch.value) {
      skipNextInputWatch.value = false
      return
    }
    scheduleSearch()
  })

  function clearSearch() {
    skipNextInputWatch.value = true
    runSearchNow()
  }

  function handleSearchFieldChange() {
    if (!input.value.trim()) return
    skipNextInputWatch.value = true
    input.value = ''
    runSearchNow()
  }

  function resetSearch(value = '') {
    cancelSearch()
    appliedSearch.value = value
    if (input.value === value) return
    skipNextInputWatch.value = true
    input.value = value
  }

  return {
    appliedSearch,
    cancelSearch,
    clearSearch,
    handleSearchFieldChange,
    resetSearch,
    runSearchNow,
  }
}
