// @vitest-environment jsdom

import { defineComponent, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import { describe, expect, it } from 'vitest'
import { en } from '../locales/en'
import ExactKeywordConfirmInput from './ExactKeywordConfirmInput.vue'

function mountInput() {
  const Host = defineComponent({
    components: { ExactKeywordConfirmInput },
    setup() {
      return { value: ref('') }
    },
    template: `
      <ExactKeywordConfirmInput
        v-model="value"
        keyword="DELETE"
        hint="Confirm deletion"
      />
    `,
  })
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en } })
  return mount(Host, { global: { plugins: [ElementPlus, i18n] } })
}

describe('ExactKeywordConfirmInput', () => {
  it('rejects different capitalization', async () => {
    const wrapper = mountInput()
    await wrapper.find('input').setValue('delete')

    expect(wrapper.text()).toContain('Capitalization does not match')
  })

  it('rejects leading and trailing spaces', async () => {
    const wrapper = mountInput()
    await wrapper.find('input').setValue('DELETE ')

    expect(wrapper.text()).toContain('Remove all leading and trailing spaces')
  })

  it('emits confirm only for an exact match', async () => {
    const wrapper = mountInput()
    const input = wrapper.find('input')
    await input.setValue('DELETE ')
    await input.trigger('keyup.enter')
    expect(wrapper.findComponent(ExactKeywordConfirmInput).emitted('confirm')).toBeUndefined()

    await input.setValue('DELETE')
    await input.trigger('keyup.enter')
    expect(wrapper.findComponent(ExactKeywordConfirmInput).emitted('confirm')).toHaveLength(1)
  })
})
