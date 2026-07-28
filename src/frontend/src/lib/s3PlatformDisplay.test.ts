// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'
import {
  DEFAULT_S3_OBJECT_PREFIX,
  distinctS3EndpointPair,
  normalizeS3ObjectPrefix,
} from './s3PlatformDisplay'
import AddS3Repo from '../pages/node/AddS3Repo.vue'

const fetchStorageProviderCatalog = vi.hoisted(() => vi.fn().mockResolvedValue({
  schema_version: 1,
  providers: [
    {
      id: 'aws',
      display_name: 'Amazon S3',
      enabled: true,
      regions: [{
        id: 'us-east-1',
        display_name: 'US East (N. Virginia)',
        region_group: 'north_america',
        region_group_en: 'North America',
        external_endpoint: 's3.amazonaws.com',
        internal_endpoint: 's3.amazonaws.com',
        driver: 's3',
        s3_url_style: 'virtual_hosted',
        use_tls: true,
      }],
    },
    {
      id: 'aliyun',
      display_name: 'Alibaba Cloud OSS',
      enabled: true,
      regions: [
        {
          id: 'cn-hangzhou',
          display_name: 'China East 1 (Hangzhou)',
          region_group: 'asia_pacific',
          region_group_en: 'Asia Pacific',
          external_endpoint: 'oss-cn-hangzhou.aliyuncs.com',
          internal_endpoint: 'oss-cn-hangzhou-internal.aliyuncs.com',
          driver: 's3',
          s3_url_style: 'virtual_hosted',
          use_tls: true,
        },
        {
          id: 'us-east-1',
          display_name: 'US East 1 (Virginia)',
          region_group: 'north_america',
          region_group_en: 'North America',
          external_endpoint: 'oss-us-east-1.aliyuncs.com',
          internal_endpoint: 'oss-us-east-1-internal.aliyuncs.com',
          driver: 's3',
          s3_url_style: 'virtual_hosted',
          use_tls: true,
        },
      ],
    },
    {
      id: 'huaweicloud',
      display_name: 'Huawei Cloud OBS',
      enabled: true,
      regions: [{
        id: 'cn-north-1',
        display_name: 'CN North-Beijing1',
        region_group: 'asia_pacific',
        region_group_en: 'Asia Pacific',
        external_endpoint: 'obs.cn-north-1.myhuaweicloud.com',
        internal_endpoint: 'obs.cn-north-1.myhuaweicloud.com',
        driver: 's3',
        s3_url_style: 'virtual_hosted',
        use_tls: true,
      }],
    },
  ],
}))

vi.mock('./storageProviderCatalogApi', () => ({ fetchStorageProviderCatalog }))

vi.mock('vue-router', async (importOriginal) => ({
  ...await importOriginal<typeof import('vue-router')>(),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('vue-i18n', async (importOriginal) => ({
  ...await importOriginal<typeof import('vue-i18n')>(),
  useI18n: () => ({ t: (key: string) => key }),
}))

describe('S3 object prefix defaults', () => {
  it('returns only a complete, genuinely distinct external/internal Endpoint pair', () => {
    expect(distinctS3EndpointPair(
      'https://oss-cn-hangzhou.aliyuncs.com',
      'oss-cn-hangzhou-internal.aliyuncs.com',
    )).toEqual({
      external: 'oss-cn-hangzhou.aliyuncs.com',
      internal: 'oss-cn-hangzhou-internal.aliyuncs.com',
    })
    expect(distinctS3EndpointPair('S3.EXAMPLE.COM.', 's3.example.com')).toBeNull()
    expect(distinctS3EndpointPair('s3.example.com', '')).toBeNull()
  })

  it('uses the stable HyperFileLens namespace by default', () => {
    expect(DEFAULT_S3_OBJECT_PREFIX).toBe('hfl/')
    expect(normalizeS3ObjectPrefix(DEFAULT_S3_OBJECT_PREFIX)).toBe('hfl/')
  })

  it('pre-fills the Add Object Storage Repository prefix input', async () => {
    const wrapper = mount(AddS3Repo, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          S3PlatformBrandIcon: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.findAll('input').map((input) => input.element.value))
      .toContain(DEFAULT_S3_OBJECT_PREFIX)
    wrapper.unmount()
  })

  it('loads official managed Provider names from the Catalog and keeps custom available', async () => {
    const wrapper = mount(AddS3Repo, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          S3PlatformBrandIcon: true,
        },
      },
    })
    await flushPromises()
    const platformButtons = wrapper.findAll('.add-s3-platform-btn')

    expect(platformButtons.map((button) => button.text())).toEqual([
      'Amazon S3',
      'Alibaba Cloud OSS',
      'Huawei Cloud OBS',
      'addS3Repo.platformOtherS3',
    ])
    expect(platformButtons.filter((button) => button.classes().includes('add-s3-platform-btn--disabled')))
      .toHaveLength(0)

    await platformButtons[0].trigger('click')
    expect(platformButtons[0].classes()).toContain('add-s3-platform-btn--active')
    expect(platformButtons[3].classes()).not.toContain('add-s3-platform-btn--active')
    wrapper.unmount()
  })

  it('groups Regions while repository creation always uses the external Endpoint', async () => {
    const wrapper = mount(AddS3Repo, {
      global: {
        plugins: [ElementPlus],
        stubs: { S3PlatformBrandIcon: true },
      },
    })
    await flushPromises()
    const platformButtons = wrapper.findAll('.add-s3-platform-btn')

    await platformButtons[0].trigger('click')
    expect(wrapper.findAll('.fullscreen-form-field').some((item) => (
      item.text().includes('addS3Repo.fieldEndpointType')
    ))).toBe(false)

    await platformButtons[1].trigger('click')
    expect(wrapper.findAll('.add-s3-region-group__title').map((item) => item.text()))
      .toEqual(['Asia Pacific', 'North America'])
    const endpointTypeField = wrapper.findAll('.fullscreen-form-field').find((item) => (
      item.text().includes('addS3Repo.fieldEndpointType')
    ))
    expect(endpointTypeField).toBeUndefined()
    expect(wrapper.findAll('input').some((input) => (
      input.element.value === 'oss-cn-hangzhou.aliyuncs.com'
    ))).toBe(true)
    wrapper.unmount()
  })
})
