import { describe, expect, it } from 'vitest'
import {
  S3_PROVIDER_OPTIONS,
  defaultS3UrlStyle,
  groupS3RegionPresets,
  isS3ProviderEnabled,
  normalizeS3StoragePlatform,
  normalizeS3UrlStyle,
  s3ProviderRegions,
} from './s3ProviderProfiles'

describe('S3 provider profiles', () => {
  it('orders supported providers and keeps future capabilities disabled', () => {
    expect(S3_PROVIDER_OPTIONS.map((provider) => provider.value)).toEqual(['other'])
    expect(S3_PROVIDER_OPTIONS.filter((provider) => provider.enabled).map((provider) => provider.value)).toEqual(['other'])
    expect(isS3ProviderEnabled('tencent')).toBe(false)
    expect(isS3ProviderEnabled('azure')).toBe(false)
    expect(isS3ProviderEnabled('gcp')).toBe(false)
  })

  it('leaves managed Provider URL style to the Catalog', () => {
    expect(defaultS3UrlStyle('huaweicloud')).toBe('auto')
    expect(defaultS3UrlStyle('aws')).toBe('auto')
    expect(defaultS3UrlStyle('aliyun')).toBe('auto')
    expect(defaultS3UrlStyle('other')).toBe('auto')
  })

  it('normalizes the custom provider and URL style values', () => {
    expect(normalizeS3StoragePlatform('other')).toBe('custom')
    expect(normalizeS3StoragePlatform('tencent')).toBe('tencent')
    expect(normalizeS3UrlStyle('virtual-hosted')).toBe('virtual_hosted')
    expect(normalizeS3UrlStyle('', 'huaweicloud')).toBe('auto')
  })

  it('does not embed managed Provider region facts', () => {
    expect(s3ProviderRegions('aws')).toEqual([])
    expect(s3ProviderRegions('aliyun')).toEqual([])
    expect(s3ProviderRegions('huaweicloud')).toEqual([])
    expect(s3ProviderRegions('other')).toEqual([])
  })

  it('groups Regions by first appearance without changing configured order', () => {
    const regions = [
      { key: 'ap-1', label: 'AP 1', region: 'ap-1', regionGroup: 'asia', regionGroupLabel: 'Asia' },
      { key: 'eu-1', label: 'EU 1', region: 'eu-1', regionGroup: 'europe', regionGroupLabel: 'Europe' },
      { key: 'ap-2', label: 'AP 2', region: 'ap-2', regionGroup: 'asia', regionGroupLabel: 'Asia' },
    ].map((region) => ({
      ...region,
      endpoint: `${region.key}.example.com`,
      externalEndpoint: `${region.key}.example.com`,
      internalEndpoint: `${region.key}.internal.example.com`,
      endpointType: 'external' as const,
      s3UrlStyle: 'virtual_hosted' as const,
      useTls: true as const,
    }))

    const groups = groupS3RegionPresets(regions)

    expect(groups.map((group) => group.key)).toEqual(['asia', 'europe'])
    expect(groups[0].regions.map((region) => region.key)).toEqual(['ap-1', 'ap-2'])
    expect(groups[1].regions.map((region) => region.key)).toEqual(['eu-1'])
  })
})
