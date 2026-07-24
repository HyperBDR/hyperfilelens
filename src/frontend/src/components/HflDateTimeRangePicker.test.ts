// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { nextTick } from 'vue'
import { describe, expect, it } from 'vitest'
import HflDateTimeRangePicker from './HflDateTimeRangePicker.vue'

describe('HflDateTimeRangePicker accessibility', () => {
  it('gives both range inputs unique ids, names, and an accessible label', async () => {
    const wrapper = mount(HflDateTimeRangePicker, {
      props: {
        label: 'Monitor time range',
        clearText: 'Clear',
        applyText: 'Apply',
      },
      global: { plugins: [ElementPlus] },
    })
    await nextTick()

    const inputs = wrapper.findAll('input.el-range-input')
    expect(inputs).toHaveLength(2)

    const ids = inputs.map((input) => input.attributes('id'))
    const names = inputs.map((input) => input.attributes('name'))
    expect(ids.every(Boolean)).toBe(true)
    expect(names.every(Boolean)).toBe(true)
    expect(new Set(ids).size).toBe(2)
    expect(new Set(names).size).toBe(2)
    expect(inputs.map((input) => input.attributes('aria-label'))).toEqual([
      'Monitor time range',
      'Monitor time range',
    ])
  })
})
