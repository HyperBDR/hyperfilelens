// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import ElementPlus, { ElOption, ElRadio, ElRadioGroup, ElSelect } from 'element-plus'
import { Archive, CircleOff, Scale } from 'lucide-vue-next'
import { describe, expect, it } from 'vitest'
import HflHelpTip from '../../../components/HflHelpTip.vue'
import CompressionLevelSelector from './CompressionLevelSelector.vue'

const options = [
  { value: 'none' as const, title: 'None', description: 'No compression', tooltip: 'None tooltip', icon: CircleOff },
  { value: 'balanced' as const, title: 'Balanced', description: 'Balanced compression', tooltip: 'Balanced tooltip', icon: Scale },
  { value: 'high' as const, title: 'High', description: 'High compression', tooltip: 'High tooltip', icon: Archive },
]

describe('CompressionLevelSelector', () => {
  it('renders all radio options, descriptions, and tooltips', () => {
    const wrapper = mount(CompressionLevelSelector, {
      props: {
        modelValue: 'balanced',
        options,
        ariaLabel: 'Compression',
      },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.findAllComponents(ElRadio)).toHaveLength(3)
    expect(wrapper.findAllComponents(HflHelpTip)).toHaveLength(3)
    expect(wrapper.text()).toContain('Balanced compression')
    expect(wrapper.find('.create-compression-radio-option--active').text()).toContain('Balanced')
  })

  it('emits a validated radio value', () => {
    const wrapper = mount(CompressionLevelSelector, {
      props: {
        modelValue: 'balanced',
        options,
        ariaLabel: 'Compression',
      },
      global: { plugins: [ElementPlus] },
    })

    wrapper.findComponent(ElRadioGroup).vm.$emit('update:modelValue', 'high')

    expect(wrapper.emitted('update:modelValue')).toEqual([['high']])
  })

  it('renders the batch select with the same option details', () => {
    const wrapper = mount(CompressionLevelSelector, {
      props: {
        modelValue: '',
        options,
        mode: 'select',
        clearable: true,
        ariaLabel: 'Compression',
      },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.findComponent(ElSelect).exists()).toBe(true)
    const selectOptions = wrapper.findAllComponents(ElOption)
    const helpTips = wrapper.findAllComponents(HflHelpTip)
    expect(selectOptions).toHaveLength(3)
    expect(selectOptions.map((option) => option.props('label'))).toEqual(['None', 'Balanced', 'High'])
    expect(helpTips).toHaveLength(3)
    expect(helpTips.map((tip) => tip.props('content'))).toContain('High tooltip')
    expect(wrapper.findComponent(ElSelect).props('clearable')).toBe(true)
    expect(wrapper.findComponent(ElSelect).props('placement')).toBe('bottom-start')
    expect(wrapper.findComponent(ElSelect).props('fallbackPlacements')).toEqual(['bottom-start', 'bottom-end'])
    expect(wrapper.findAllComponents(CircleOff)).toHaveLength(1)
    expect(wrapper.findAllComponents(Scale)).toHaveLength(1)
    expect(wrapper.findAllComponents(Archive)).toHaveLength(1)
  })

  it('renders a required select by default', () => {
    const wrapper = mount(CompressionLevelSelector, {
      props: {
        modelValue: 'balanced',
        options,
        mode: 'select',
        ariaLabel: 'Compression',
      },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.findComponent(ElSelect).props('clearable')).toBe(false)
    expect(wrapper.find('.compression-select-label .compression-level-icon--balanced').exists()).toBe(true)
    expect(wrapper.find('.compression-select-label__text').text()).toBe('Balanced')
  })

  it('emits an empty batch value when the select is cleared', () => {
    const wrapper = mount(CompressionLevelSelector, {
      props: {
        modelValue: 'high',
        options,
        mode: 'select',
        clearable: true,
        ariaLabel: 'Compression',
      },
      global: { plugins: [ElementPlus] },
    })

    wrapper.findComponent(ElSelect).vm.$emit('update:modelValue', '')

    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
  })
})
