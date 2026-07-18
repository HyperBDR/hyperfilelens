// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { describe, expect, it } from 'vitest'
import FlowSourceSummaryCell from './FlowSourceSummaryCell.vue'
import type { FlowSourceRow } from '../composables/useFlowSourceAggregate'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      protection: {
        backupsPage: {
          sourceTypeHost: 'Host',
          sourceTypeNas: 'NAS',
        },
      },
    },
  },
})

const row: FlowSourceRow = {
  id: 'agent:81',
  name: 'hyperbdr81',
  hostname: 'hyperbdr81',
  nodeName: 'hyperbdr81',
  nodeIp: '192.168.65.1',
  status: 'online',
  registeredAt: '2026-07-14T17:56:27Z',
  type: 'host',
}

function mountCell(interactive?: boolean, externallyInteractive?: boolean) {
  return mount(FlowSourceSummaryCell, {
    props: { row, interactive, externallyInteractive },
    global: { plugins: [i18n] },
  })
}

describe('FlowSourceSummaryCell', () => {
  it('renders a static backup source summary when interaction is disabled', async () => {
    const wrapper = mountCell(false)

    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.classes()).not.toContain('backup-source-cell--clickable')
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find('.backup-source-cell__name').exists()).toBe(true)
    expect(wrapper.find('.hfl-table-name-link').exists()).toBe(false)

    await wrapper.trigger('click')

    expect(wrapper.emitted('open')).toBeUndefined()
  })

  it('keeps the default summary interactive', async () => {
    const wrapper = mountCell()

    expect(wrapper.element.tagName).toBe('BUTTON')
    expect(wrapper.classes()).toContain('backup-source-cell--clickable')

    await wrapper.trigger('click')

    expect(wrapper.emitted('open')).toEqual([[row]])
  })

  it('keeps the clickable appearance when a parent owns the interaction', async () => {
    const wrapper = mountCell(false, true)

    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.classes()).toContain('backup-source-cell--clickable')
    expect(wrapper.find('.hfl-table-name-link').exists()).toBe(true)

    await wrapper.trigger('click')

    expect(wrapper.emitted('open')).toBeUndefined()
  })
})
