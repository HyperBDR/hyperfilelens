// @vitest-environment jsdom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ModulePage from './ModulePage.vue'

const route = vi.hoisted(() => ({
  path: '/platform-ops/monitoring/tasks',
  query: {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => route,
}))

const SidebarStub = defineComponent({
  props: {
    collapsed: { type: Boolean, default: false },
    menus: { type: Array, required: true },
  },
  emits: ['toggle'],
  template: `
    <button
      class="sidebar-stub"
      :data-collapsed="String(collapsed)"
      type="button"
      @click="$emit('toggle')"
    />
  `,
})

function setViewportWidth(width: number) {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    value: width,
  })
  window.dispatchEvent(new Event('resize'))
}

describe('ModulePage responsive sidebar', () => {
  beforeEach(() => {
    localStorage.clear()
    route.path = '/platform-ops/monitoring/tasks'
    setViewportWidth(1200)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps mobile visibility separate from the desktop collapse preference', async () => {
    localStorage.setItem('sidebar-collapsed', 'false')
    setViewportWidth(800)
    const wrapper = mount(ModulePage, {
      props: {
        menus: [{ label: 'Tasks', to: '/platform-ops/monitoring/tasks' }],
      },
      global: {
        stubs: { Sidebar: SidebarStub },
      },
    })
    await nextTick()

    const sidebar = wrapper.get('.sidebar-stub')
    expect(sidebar.attributes('data-collapsed')).toBe('false')
    expect(localStorage.getItem('sidebar-collapsed')).toBe('false')

    setViewportWidth(1200)
    await nextTick()
    expect(sidebar.attributes('data-collapsed')).toBe('false')

    await sidebar.trigger('click')
    expect(sidebar.attributes('data-collapsed')).toBe('true')
    expect(localStorage.getItem('sidebar-collapsed')).toBe('true')

    wrapper.unmount()
  })

  it('pairs the hidden mobile sidebar with the shell navigation drawer', () => {
    const modulePageSource = readFileSync(
      resolve(process.cwd(), 'src/components/ModulePage.vue'),
      'utf8',
    )
    const shellSource = readFileSync(
      resolve(process.cwd(), 'src/platform-ops/layout/PlatformOpsShell.vue'),
      'utf8',
    )

    expect(modulePageSource).toMatch(
      /@media \(max-width: 1023\.98px\)[\s\S]*?\.sidebar-wrapper\s*{[\s\S]*?display:\s*none/,
    )
    expect(shellSource).toContain('<MobileNavigationDrawer')
    expect(shellSource).toMatch(
      /@media \(max-width: 1023\.98px\)[\s\S]*?\.platform-ops-header__menu\s*{[\s\S]*?display:\s*inline-flex/,
    )
  })
})
