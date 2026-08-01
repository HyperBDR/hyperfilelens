// @vitest-environment jsdom

import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { describe, expect, it } from 'vitest'
import { en } from '../locales/en'
import BackupSourceUnregisterDialogBody from './BackupSourceUnregisterDialogBody.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: { en },
})
const ElCheckboxStub = defineComponent({
  props: { modelValue: Boolean, disabled: Boolean },
  emits: ['update:modelValue'],
  template: `
    <input
      data-test="force-checkbox"
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      @change="$emit('update:modelValue', !modelValue)"
    >
  `,
})

const ElAlertStub = defineComponent({
  template: '<section data-test="preflight-alert"><slot name="title" /><slot /></section>',
})

const ElButtonStub = defineComponent({
  props: { disabled: Boolean },
  emits: ['click'],
  template: '<button data-test="retry" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
})

function mountBody(props: Record<string, unknown> = {}) {
  return mount(BackupSourceUnregisterDialogBody, {
    props: {
      sourceIds: ['agent:25'],
      preflight: null,
      ...props,
    },
    global: {
      plugins: [i18n],
      directives: { tableOverflowTitle: {} },
      stubs: {
        ElAlert: ElAlertStub,
        ElButton: ElButtonStub,
        ElCheckbox: ElCheckboxStub,
        ElTable: defineComponent({ template: '<div />' }),
        ElTableColumn: defineComponent({ template: '<div />' }),
        ElTag: defineComponent({ template: '<span><slot /></span>' }),
        AgentPlatformBrandIcon: defineComponent({ template: '<span />' }),
        ExactKeywordConfirmInput: defineComponent({ template: '<input data-test="confirmation">' }),
      },
    },
  })
}

describe('BackupSourceUnregisterDialogBody', () => {
  it('always renders an independently selectable Force Cleanup option', () => {
    const wrapper = mountBody({ preflightLoading: true })
    expect(wrapper.find('.hfl-flow-action-dialog__force-panel').exists()).toBe(true)
    expect(wrapper.get('[data-test="force-checkbox"]').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('only disables mode changes while the delete request is submitting', () => {
    const wrapper = mountBody({ loading: true })
    expect(wrapper.get('[data-test="force-checkbox"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('shows a retry action when prerequisite verification fails', async () => {
    const wrapper = mountBody({ preflightError: true })
    expect(wrapper.find('[data-test="preflight-alert"]').exists()).toBe(true)
    await wrapper.get('[data-test="retry"]').trigger('click')
    expect(wrapper.emitted('retry-preflight')).toHaveLength(1)
    wrapper.unmount()
  })
})
