export type S3UrlStyle = 'auto' | 'virtual_hosted' | 'path'
export type S3StoragePlatform = string
export type S3PlatformSelection = string
export type S3PlatformCapability = string

export interface S3ProviderOption {
  value: S3PlatformCapability
  labelKey?: string
  label?: string
  enabled: boolean
}

export interface S3RegionPreset {
  key: string
  label: string
  endpoint: string
  externalEndpoint: string
  internalEndpoint: string
  endpointType: 'external' | 'internal'
  region: string
  regionGroup: string
  regionGroupLabel: string
  s3UrlStyle: Exclude<S3UrlStyle, 'auto'>
  useTls: true
}

export interface S3RegionGroup {
  key: string
  label: string
  regions: S3RegionPreset[]
}

export const S3_PROVIDER_OPTIONS: S3ProviderOption[] = [
  { value: 'other', labelKey: 'addS3Repo.platformOtherS3', enabled: true },
]

export function isS3ProviderEnabled(platform: S3PlatformCapability): platform is S3PlatformSelection {
  return S3_PROVIDER_OPTIONS.some((item) => item.value === platform && item.enabled)
}

export function s3ProviderRegions(platform: S3PlatformSelection | undefined): S3RegionPreset[] {
  void platform
  return []
}

export function groupS3RegionPresets(regions: S3RegionPreset[]): S3RegionGroup[] {
  const groups = new Map<string, S3RegionGroup>()
  for (const region of regions) {
    const group = groups.get(region.regionGroup) || {
      key: region.regionGroup,
      label: region.regionGroupLabel,
      regions: [],
    }
    group.regions.push(region)
    groups.set(region.regionGroup, group)
  }
  return [...groups.values()]
}

export function defaultS3UrlStyle(platform: S3PlatformSelection | S3StoragePlatform | undefined): S3UrlStyle {
  void platform
  return 'auto'
}

export function normalizeS3StoragePlatform(platform: S3PlatformSelection | undefined): S3StoragePlatform {
  return platform === 'other' || !platform ? 'custom' : platform
}

export function normalizeS3UrlStyle(value: unknown, platform?: S3PlatformSelection | S3StoragePlatform): S3UrlStyle {
  const normalized = String(value || '').trim().toLowerCase().replace(/-/g, '_')
  if (normalized === 'auto' || normalized === 'virtual_hosted' || normalized === 'path') return normalized
  return defaultS3UrlStyle(platform)
}
