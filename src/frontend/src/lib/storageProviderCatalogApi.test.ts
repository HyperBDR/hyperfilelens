// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import {
  applyProviderImport,
  createProviderValidationRun,
  normalizedStorageProviderSnapshot,
  reviewProviderReset,
  type ProviderImportReview,
} from './storageProviderCatalogApi'

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()
  return { ...actual, api: vi.fn() }
})

afterEach(() => vi.clearAllMocks())

describe('Storage Provider Catalog API', () => {
  it('submits credentials only to the write-only validation endpoint', async () => {
    vi.mocked(api).mockResolvedValue({ id: 'run-1' })

    await createProviderValidationRun({
      provider_id: 'aliyun',
      region_ids: ['oss-cn-hangzhou'],
      access_key_id: 'access-value',
      secret_access_key: 'secret-value',
      candidate_config: {
        id: 'aliyun',
        display_name: 'Alibaba Cloud OSS',
        enabled: true,
        regions: [],
      },
    })

    expect(api).toHaveBeenCalledWith('/api/v1/platform-ops/storage-provider-validation-runs', {
      method: 'POST',
      body: JSON.stringify({
        provider_id: 'aliyun',
        region_ids: ['oss-cn-hangzhou'],
        access_key_id: 'access-value',
        secret_access_key: 'secret-value',
        candidate_config: {
          id: 'aliyun',
          display_name: 'Alibaba Cloud OSS',
          enabled: true,
          regions: [],
        },
      }),
    })
  })

  it('re-submits the reviewed document, checksum, token, and exact risks for Apply', async () => {
    vi.mocked(api).mockResolvedValue({ applied: true })
    const review = {
      input_checksum: 'a'.repeat(64),
      review_token: 'opaque-review-token',
    } as ProviderImportReview

    await applyProviderImport('{"schema_version":1,"providers":[]}', review, ['validation:not_run:aliyun'])

    expect(api).toHaveBeenCalledWith('/api/v1/platform-ops/storage-providers/import/apply', {
      method: 'POST',
      body: JSON.stringify({
        content: '{"schema_version":1,"providers":[]}',
        input_checksum: 'a'.repeat(64),
        review_token: 'opaque-review-token',
        risk_confirmations: ['validation:not_run:aliyun'],
      }),
    })
  })

  it('uses distinct server Review endpoints for Provider and all-Provider reset', async () => {
    vi.mocked(api).mockResolvedValue({ scope: 'all' })

    await reviewProviderReset('aliyun')
    await reviewProviderReset()

    expect(vi.mocked(api).mock.calls.map(([path]) => path)).toEqual([
      '/api/v1/platform-ops/storage-providers/aliyun/reset/review',
      '/api/v1/platform-ops/storage-providers/reset/review',
    ])
  })

  it('compares validation candidates after server-equivalent string normalization', () => {
    const candidate = {
      regions: [{
        use_tls: true as const,
        s3_url_style: 'virtual_hosted' as const,
        driver: 's3' as const,
        internal_endpoint: ' OBS-CN.EXAMPLE.COM ',
        external_endpoint: ' OBS-CN.EXAMPLE.COM ',
        region_group_en: ' Asia Pacific ',
        region_group: ' asia_pacific ',
        display_name: ' Guangzhou ',
        id: ' cn-south-1 ',
      }],
      enabled: true,
      display_name: ' Huawei Cloud ',
      id: 'huaweicloud',
    }
    const normalized = {
      id: 'huaweicloud',
      display_name: 'Huawei Cloud',
      enabled: true,
      regions: [{
        id: 'cn-south-1',
        display_name: 'Guangzhou',
        region_group: 'asia_pacific',
        region_group_en: 'Asia Pacific',
        external_endpoint: 'obs-cn.example.com',
        internal_endpoint: 'obs-cn.example.com',
        driver: 's3' as const,
        s3_url_style: 'virtual_hosted' as const,
        use_tls: true as const,
      }],
    }

    expect(normalizedStorageProviderSnapshot(candidate)).toBe(
      normalizedStorageProviderSnapshot(normalized),
    )
  })
})
