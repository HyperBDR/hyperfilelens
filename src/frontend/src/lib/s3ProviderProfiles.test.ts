import { describe, expect, it } from 'vitest'
import {
  S3_PROVIDER_OPTIONS,
  defaultS3UrlStyle,
  isS3ProviderEnabled,
  normalizeS3StoragePlatform,
  normalizeS3UrlStyle,
  s3ProviderRegions,
} from './s3ProviderProfiles'

describe('S3 provider profiles', () => {
  it('orders supported providers and keeps future capabilities disabled', () => {
    expect(S3_PROVIDER_OPTIONS.map((provider) => provider.value)).toEqual([
      'aws',
      'aliyun',
      'huawei',
      'other',
      'tencent',
      'azure',
      'gcp',
    ])
    expect(S3_PROVIDER_OPTIONS.filter((provider) => provider.enabled).map((provider) => provider.value)).toEqual([
      'aws',
      'aliyun',
      'huawei',
      'other',
    ])
    expect(isS3ProviderEnabled('tencent')).toBe(false)
    expect(isS3ProviderEnabled('azure')).toBe(false)
    expect(isS3ProviderEnabled('gcp')).toBe(false)
  })

  it('uses virtual-hosted URLs for Huawei and auto for other providers', () => {
    expect(defaultS3UrlStyle('huawei')).toBe('virtual_hosted')
    expect(defaultS3UrlStyle('aws')).toBe('auto')
    expect(defaultS3UrlStyle('aliyun')).toBe('auto')
    expect(defaultS3UrlStyle('other')).toBe('auto')
  })

  it('normalizes the custom provider and URL style values', () => {
    expect(normalizeS3StoragePlatform('other')).toBe('custom')
    expect(normalizeS3UrlStyle('virtual-hosted')).toBe('virtual_hosted')
    expect(normalizeS3UrlStyle('', 'huawei')).toBe('virtual_hosted')
  })

  it('provides region endpoints for each named provider', () => {
    expect(s3ProviderRegions('aws')[0]?.endpoint).toBe('https://s3.amazonaws.com')
    expect(s3ProviderRegions('aliyun')[0]?.endpoint).toContain('aliyuncs.com')
    expect(s3ProviderRegions('huawei')[0]?.endpoint).toContain('myhuaweicloud.com')
    expect(s3ProviderRegions('other')).toEqual([])
  })
})
