// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { describe, expect, it } from 'vitest'
import TaskTypeLabel from './TaskTypeLabel.vue'

function mountLabel(emphasis?: 'primary' | 'secondary') {
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: {
      en: {
        ops: {
          task: {
            emptyMark: '—',
            taskType: { backup: 'Backup' },
          },
        },
      },
    },
  })

  return mount(TaskTypeLabel, {
    props: { type: 'backup', ...(emphasis ? { emphasis } : {}) },
    global: { plugins: [i18n] },
  })
}

describe('TaskTypeLabel', () => {
  it('uses primary emphasis for task identity by default', () => {
    const wrapper = mountLabel()

    expect(wrapper.get('.hfl-table-type-label').classes()).toContain('hfl-table-type-label--primary')
    expect(wrapper.text()).toBe('Backup')
  })

  it('can be reduced to secondary emphasis in supporting contexts', () => {
    const wrapper = mountLabel('secondary')

    expect(wrapper.get('.hfl-table-type-label').classes()).toContain('hfl-table-type-label--secondary')
  })
})
