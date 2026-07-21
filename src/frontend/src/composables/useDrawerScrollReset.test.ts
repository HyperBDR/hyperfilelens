// @vitest-environment jsdom

import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { useDrawerScrollReset } from './useDrawerScrollReset'

function mountDrawerScrollReset(withDrawerBody = true) {
  return mount(defineComponent({
    setup(_, { expose }) {
      const scrollReset = useDrawerScrollReset()
      expose(scrollReset)
      return () => {
        const anchor = h('div', { ref: scrollReset.drawerScrollAnchorRef, class: 'drawer-scroll-anchor' })
        return withDrawerBody
          ? h('div', { class: 'el-drawer__body' }, [h('div', { class: 'nested-content' }, [anchor])])
          : anchor
      }
    },
  }))
}

describe('useDrawerScrollReset', () => {
  it('resets the closest drawer body after the DOM update', async () => {
    const wrapper = mountDrawerScrollReset()
    const drawerBody = wrapper.get('.el-drawer__body').element as HTMLElement
    drawerBody.scrollTop = 320

    ;(wrapper.vm as unknown as { resetDrawerScroll: () => void }).resetDrawerScroll()
    expect(drawerBody.scrollTop).toBe(320)

    await nextTick()
    expect(drawerBody.scrollTop).toBe(0)
  })

  it('does nothing when the anchor is not inside a drawer body', async () => {
    const wrapper = mountDrawerScrollReset(false)

    expect(() => {
      ;(wrapper.vm as unknown as { resetDrawerScroll: () => void }).resetDrawerScroll()
    }).not.toThrow()

    await nextTick()
    expect(wrapper.get('.drawer-scroll-anchor').exists()).toBe(true)
  })
})
