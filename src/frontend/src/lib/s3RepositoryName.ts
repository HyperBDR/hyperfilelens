export const S3_REPOSITORY_NAME_PREFIXES = {
  other: 'S3',
  aliyun: 'OSS',
  huawei: 'OBS',
  tencent: 'COS',
  aws: 'AWS',
  azure: 'AZURE',
  gcp: 'GCS',
} as const

export function buildS3RepositoryName(platform: string | undefined, bucket: string): string {
  const prefix = platform ? S3_REPOSITORY_NAME_PREFIXES[platform as keyof typeof S3_REPOSITORY_NAME_PREFIXES] : undefined
  const bucketName = bucket.trim()
  if (!prefix) return ''
  return bucketName ? `${prefix}(${bucketName})` : prefix
}
