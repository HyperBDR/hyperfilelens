// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { ElTag } from 'element-plus'
import { describe, expect, it } from 'vitest'
import HflBooleanStatusTag from './HflBooleanStatusTag.vue'

const global = { components: { ElTag } }

describe('HflBooleanStatusTag', () => {
  it('renders enabled values with the global success tone', () => {
    const wrapper = mount(HflBooleanStatusTag, {
      props: { value: true, label: 'Enabled' },
      global,
    })

    expect(wrapper.get('.el-tag').classes()).toContain('el-tag--success')
    expect(wrapper.html()).toContain('hfl-tag--boolean')
  })

  it('renders disabled values with the global neutral tone', () => {
    const wrapper = mount(HflBooleanStatusTag, {
      props: { value: false, label: 'Disabled' },
      global,
    })

    expect(wrapper.html()).toContain('hfl-tag--neutral')
    expect(wrapper.get('.el-tag').classes()).not.toContain('el-tag--info')
  })
})
