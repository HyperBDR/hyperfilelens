import { describe, expect, it } from 'vitest'
import {
  defaultS3UrlStyle,
  normalizeS3StoragePlatform,
  normalizeS3UrlStyle,
  s3ProviderRegions,
} from './s3ProviderProfiles'

describe('S3 provider profiles', () => {
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
