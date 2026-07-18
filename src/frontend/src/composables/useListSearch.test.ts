// @vitest-environment jsdom

import { defineComponent, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useListSearch } from './useListSearch'

function mountSearch() {
  const action = vi.fn()
  const wrapper = mount(defineComponent({
    setup(_, { expose }) {
      const input = ref('')
      const search = useListSearch(input, action)
      expose({ input, ...search })
      return () => null
    },
  }))
  return { action, wrapper }
}

describe('useListSearch', () => {
  beforeEach(() => vi.useFakeTimers())

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('debounces typed input and applies only the latest value', async () => {
    const { action, wrapper } = mountSearch()
    const vm = wrapper.vm as unknown as { input: string; appliedSearch: string }

    vm.input = 'a'
    await nextTick()
    vi.advanceTimersByTime(500)
    vm.input = 'agent'
    await nextTick()
    vi.advanceTimersByTime(899)

    expect(action).not.toHaveBeenCalled()
    expect(vm.appliedSearch).toBe('')

    vi.advanceTimersByTime(1)
    expect(action).toHaveBeenCalledTimes(1)
    expect(vm.appliedSearch).toBe('agent')
    wrapper.unmount()
  })

  it('applies clear immediately and cancels the pending search', async () => {
    const { action, wrapper } = mountSearch()
    const vm = wrapper.vm as unknown as {
      input: string
      appliedSearch: string
      clearSearch: () => void
    }

    vm.input = 'agent'
    await nextTick()
    vm.input = ''
    vm.clearSearch()
    await nextTick()

    expect(action).toHaveBeenCalledTimes(1)
    expect(vm.appliedSearch).toBe('')
    vi.advanceTimersByTime(900)
    expect(action).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('allows an external select filter to apply the current search immediately', async () => {
    const { action, wrapper } = mountSearch()
    const vm = wrapper.vm as unknown as {
      input: string
      appliedSearch: string
      runSearchNow: () => void
    }

    vm.input = 'agent'
    await nextTick()
    vm.runSearchNow()

    expect(action).toHaveBeenCalledTimes(1)
    expect(vm.appliedSearch).toBe('agent')
    vi.advanceTimersByTime(900)
    expect(action).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('clears a non-empty query and applies exactly once when the search field changes', async () => {
    const { action, wrapper } = mountSearch()
    const vm = wrapper.vm as unknown as {
      input: string
      appliedSearch: string
      handleSearchFieldChange: () => void
    }

    vm.input = 'agent'
    await nextTick()
    vm.handleSearchFieldChange()
    await nextTick()

    expect(vm.input).toBe('')
    expect(vm.appliedSearch).toBe('')
    expect(action).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(900)
    expect(action).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('does not apply or update the table when the search field changes with an empty query', () => {
    const { action, wrapper } = mountSearch()
    const vm = wrapper.vm as unknown as {
      appliedSearch: string
      handleSearchFieldChange: () => void
    }

    vm.handleSearchFieldChange()

    expect(action).not.toHaveBeenCalled()
    expect(vm.appliedSearch).toBe('')
    wrapper.unmount()
  })
})
