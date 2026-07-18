// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_S3_OBJECT_PREFIX, normalizeS3ObjectPrefix } from './s3PlatformDisplay'
import AddS3Repo from '../pages/node/AddS3Repo.vue'

vi.mock('vue-router', async (importOriginal) => ({
  ...await importOriginal<typeof import('vue-router')>(),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('vue-i18n', async (importOriginal) => ({
  ...await importOriginal<typeof import('vue-i18n')>(),
  useI18n: () => ({ t: (key: string) => key }),
}))

describe('S3 object prefix defaults', () => {
  it('uses the stable HyperFileLens namespace by default', () => {
    expect(DEFAULT_S3_OBJECT_PREFIX).toBe('hfl/')
    expect(normalizeS3ObjectPrefix(DEFAULT_S3_OBJECT_PREFIX)).toBe('hfl/')
  })

  it('pre-fills the Add Object Storage Repository prefix input', () => {
    const wrapper = mount(AddS3Repo, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          S3PlatformBrandIcon: true,
        },
      },
    })

    expect(wrapper.findAll('input').map((input) => input.element.value))
      .toContain(DEFAULT_S3_OBJECT_PREFIX)
  })
})
