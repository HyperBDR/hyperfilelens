// @vitest-environment jsdom

import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PlatformOpsPagination from './PlatformOpsPagination.vue'

const HflPaginationStub = defineComponent({
  name: 'HflPagination',
  props: {
    currentPage: { type: Number, required: true },
    pageSize: { type: Number, required: true },
    pageSizes: { type: Array, required: true },
    total: { type: Number, required: true },
    layout: { type: String, required: true },
  },
  emits: ['update:currentPage', 'update:pageSize'],
  template: '<div class="pagination-stub" />',
})

function mountPagination(currentPage = 3) {
  return mount(PlatformOpsPagination, {
    props: {
      currentPage,
      pageSize: 20,
      total: 120,
    },
    global: {
      stubs: { HflPagination: HflPaginationStub },
    },
  })
}

describe('PlatformOpsPagination', () => {
  it('applies the ordinary-user list pagination standard', () => {
    const wrapper = mountPagination()
    const pagination = wrapper.getComponent(HflPaginationStub)

    expect(pagination.classes()).toContain('hfl-list-footer__pagination')
    expect(pagination.props()).toMatchObject({
      currentPage: 3,
      pageSize: 20,
      pageSizes: [20, 30, 50, 100],
      total: 120,
      layout: 'total, sizes, prev, pager, next',
    })
  })

  it('returns to the first page before changing page size', async () => {
    const wrapper = mountPagination()

    wrapper.getComponent(HflPaginationStub).vm.$emit('update:pageSize', 50)
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:currentPage')).toEqual([[1]])
    expect(wrapper.emitted('update:pageSize')).toEqual([[50]])
  })

  it('does not emit a redundant page update when already on the first page', async () => {
    const wrapper = mountPagination(1)

    wrapper.getComponent(HflPaginationStub).vm.$emit('update:pageSize', 30)
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:currentPage')).toBeUndefined()
    expect(wrapper.emitted('update:pageSize')).toEqual([[30]])
  })
})
