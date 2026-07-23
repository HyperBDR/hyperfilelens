// @vitest-environment jsdom

import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import ModulePage from './ModulePage.vue'

const EmptyRoute = defineComponent({ template: '<div />' })

describe('ModulePage scroll reset', () => {
  it('returns its scroll containers to the top after navigation', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/one', component: EmptyRoute },
        { path: '/two', component: EmptyRoute },
      ],
    })
    await router.push('/one')
    await router.isReady()

    const wrapper = mount(ModulePage, {
      global: {
        plugins: [router],
        stubs: { Sidebar: true },
      },
    })
    const mainContent = wrapper.get('.main-content').element
    const pageBody = wrapper.get('.page-body').element
    mainContent.scrollTop = 80
    pageBody.scrollTop = 120

    await router.push('/two')
    await flushPromises()

    expect(mainContent.scrollTop).toBe(0)
    expect(pageBody.scrollTop).toBe(0)
    wrapper.unmount()
  })
})
