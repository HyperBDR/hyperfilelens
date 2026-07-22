export type S3UrlStyle = 'auto' | 'virtual_hosted' | 'path'
export type S3StoragePlatform = 'aliyun' | 'huawei' | 'aws' | 'custom'
export type S3PlatformSelection = Exclude<S3StoragePlatform, 'custom'> | 'other'
export type S3PlatformCapability = S3PlatformSelection | 'tencent' | 'azure' | 'gcp'

export interface S3ProviderOption {
  value: S3PlatformCapability
  labelKey: string
  enabled: boolean
}

export interface S3RegionPreset {
  key: string
  labelKey: string
  endpoint: string
  region: string
}

const aliyunRegions: S3RegionPreset[] = [
  { key: 'cn-hangzhou', labelKey: 'addS3Repo.regionLabels.aliyunCnHangzhou', endpoint: 'https://oss-cn-hangzhou.aliyuncs.com', region: 'cn-hangzhou' },
  { key: 'cn-shanghai', labelKey: 'addS3Repo.regionLabels.aliyunCnShanghai', endpoint: 'https://oss-cn-shanghai.aliyuncs.com', region: 'cn-shanghai' },
  { key: 'cn-qingdao', labelKey: 'addS3Repo.regionLabels.aliyunCnQingdao', endpoint: 'https://oss-cn-qingdao.aliyuncs.com', region: 'cn-qingdao' },
  { key: 'cn-beijing', labelKey: 'addS3Repo.regionLabels.aliyunCnBeijing', endpoint: 'https://oss-cn-beijing.aliyuncs.com', region: 'cn-beijing' },
  { key: 'cn-shenzhen', labelKey: 'addS3Repo.regionLabels.aliyunCnShenzhen', endpoint: 'https://oss-cn-shenzhen.aliyuncs.com', region: 'cn-shenzhen' },
  { key: 'cn-heyuan', labelKey: 'addS3Repo.regionLabels.aliyunCnHeyuan', endpoint: 'https://oss-cn-heyuan.aliyuncs.com', region: 'cn-heyuan' },
  { key: 'cn-guangzhou', labelKey: 'addS3Repo.regionLabels.aliyunCnGuangzhou', endpoint: 'https://oss-cn-guangzhou.aliyuncs.com', region: 'cn-guangzhou' },
  { key: 'cn-chengdu', labelKey: 'addS3Repo.regionLabels.aliyunCnChengdu', endpoint: 'https://oss-cn-chengdu.aliyuncs.com', region: 'cn-chengdu' },
  { key: 'cn-hongkong', labelKey: 'addS3Repo.regionLabels.aliyunCnHongkong', endpoint: 'https://oss-cn-hongkong.aliyuncs.com', region: 'cn-hongkong' },
  { key: 'ap-southeast-1', labelKey: 'addS3Repo.regionLabels.aliyunApSoutheast1', endpoint: 'https://oss-ap-southeast-1.aliyuncs.com', region: 'ap-southeast-1' },
  { key: 'ap-southeast-2', labelKey: 'addS3Repo.regionLabels.aliyunApSoutheast2', endpoint: 'https://oss-ap-southeast-2.aliyuncs.com', region: 'ap-southeast-2' },
  { key: 'ap-southeast-3', labelKey: 'addS3Repo.regionLabels.aliyunApSoutheast3', endpoint: 'https://oss-ap-southeast-3.aliyuncs.com', region: 'ap-southeast-3' },
  { key: 'ap-southeast-5', labelKey: 'addS3Repo.regionLabels.aliyunApSoutheast5', endpoint: 'https://oss-ap-southeast-5.aliyuncs.com', region: 'ap-southeast-5' },
  { key: 'us-east-1', labelKey: 'addS3Repo.regionLabels.aliyunUsEast1', endpoint: 'https://oss-us-east-1.aliyuncs.com', region: 'us-east-1' },
  { key: 'us-west-1', labelKey: 'addS3Repo.regionLabels.aliyunUsWest1', endpoint: 'https://oss-us-west-1.aliyuncs.com', region: 'us-west-1' },
]

const huaweiRegions: S3RegionPreset[] = [
  { key: 'cn-north-1', labelKey: 'addS3Repo.regionLabels.huaweiCnNorth1', endpoint: 'https://obs.cn-north-1.myhuaweicloud.com', region: 'cn-north-1' },
  { key: 'cn-north-5', labelKey: 'addS3Repo.regionLabels.huaweiCnNorth5', endpoint: 'https://obs.cn-north-5.myhuaweicloud.com', region: 'cn-north-5' },
  { key: 'cn-north-9', labelKey: 'addS3Repo.regionLabels.huaweiCnNorth9', endpoint: 'https://obs.cn-north-9.myhuaweicloud.com', region: 'cn-north-9' },
  { key: 'cn-east-3', labelKey: 'addS3Repo.regionLabels.huaweiCnEast3', endpoint: 'https://obs.cn-east-3.myhuaweicloud.com', region: 'cn-east-3' },
  { key: 'cn-south-1', labelKey: 'addS3Repo.regionLabels.huaweiCnSouth1', endpoint: 'https://obs.cn-south-1.myhuaweicloud.com', region: 'cn-south-1' },
]

const awsRegions: S3RegionPreset[] = [
  { key: 'us-east-1', labelKey: 'addS3Repo.regionLabels.awsUsEast1', endpoint: 'https://s3.amazonaws.com', region: 'us-east-1' },
  { key: 'us-east-2', labelKey: 'addS3Repo.regionLabels.awsUsEast2', endpoint: 'https://s3.us-east-2.amazonaws.com', region: 'us-east-2' },
  { key: 'us-west-1', labelKey: 'addS3Repo.regionLabels.awsUsWest1', endpoint: 'https://s3.us-west-1.amazonaws.com', region: 'us-west-1' },
  { key: 'us-west-2', labelKey: 'addS3Repo.regionLabels.awsUsWest2', endpoint: 'https://s3.us-west-2.amazonaws.com', region: 'us-west-2' },
  { key: 'eu-west-1', labelKey: 'addS3Repo.regionLabels.awsEuWest1', endpoint: 'https://s3.eu-west-1.amazonaws.com', region: 'eu-west-1' },
  { key: 'eu-central-1', labelKey: 'addS3Repo.regionLabels.awsEuCentral1', endpoint: 'https://s3.eu-central-1.amazonaws.com', region: 'eu-central-1' },
  { key: 'ap-southeast-1', labelKey: 'addS3Repo.regionLabels.awsApSoutheast1', endpoint: 'https://s3.ap-southeast-1.amazonaws.com', region: 'ap-southeast-1' },
  { key: 'ap-northeast-1', labelKey: 'addS3Repo.regionLabels.awsApNortheast1', endpoint: 'https://s3.ap-northeast-1.amazonaws.com', region: 'ap-northeast-1' },
]

export const S3_PROVIDER_OPTIONS: S3ProviderOption[] = [
  { value: 'aws', labelKey: 'addS3Repo.platformAws', enabled: true },
  { value: 'aliyun', labelKey: 'addS3Repo.platformAliyun', enabled: true },
  { value: 'huawei', labelKey: 'addS3Repo.platformHuawei', enabled: true },
  { value: 'other', labelKey: 'addS3Repo.platformOtherS3', enabled: true },
  { value: 'tencent', labelKey: 'addS3Repo.platformTencent', enabled: false },
  { value: 'azure', labelKey: 'addS3Repo.platformAzure', enabled: false },
  { value: 'gcp', labelKey: 'addS3Repo.platformGcp', enabled: false },
]

export function isS3ProviderEnabled(platform: S3PlatformCapability): platform is S3PlatformSelection {
  return S3_PROVIDER_OPTIONS.some((item) => item.value === platform && item.enabled)
}

export function s3ProviderRegions(platform: S3PlatformSelection | undefined): S3RegionPreset[] {
  if (platform === 'aliyun') return aliyunRegions
  if (platform === 'huawei') return huaweiRegions
  if (platform === 'aws') return awsRegions
  return []
}

export function defaultS3UrlStyle(platform: S3PlatformSelection | S3StoragePlatform | undefined): S3UrlStyle {
  return platform === 'huawei' ? 'virtual_hosted' : 'auto'
}

export function normalizeS3StoragePlatform(platform: S3PlatformSelection | undefined): S3StoragePlatform {
  return platform === 'other' || !platform ? 'custom' : platform
}

export function normalizeS3UrlStyle(value: unknown, platform?: S3PlatformSelection | S3StoragePlatform): S3UrlStyle {
  const normalized = String(value || '').trim().toLowerCase().replace(/-/g, '_')
  if (normalized === 'auto' || normalized === 'virtual_hosted' || normalized === 'path') return normalized
  return defaultS3UrlStyle(platform)
}
