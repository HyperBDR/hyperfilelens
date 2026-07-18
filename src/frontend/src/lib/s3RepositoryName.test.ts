import { describe, expect, it } from 'vitest'
import { buildS3RepositoryName } from './s3RepositoryName'

describe('buildS3RepositoryName', () => {
  it.each([
    ['other', 'backup-prod', 'S3(backup-prod)'],
    ['aliyun', 'backup-prod', 'OSS(backup-prod)'],
    ['huawei', 'backup-prod', 'OBS(backup-prod)'],
    ['tencent', 'backup-prod', 'COS(backup-prod)'],
    ['aws', 'backup-prod', 'AWS(backup-prod)'],
    ['azure', 'backup-prod', 'AZURE(backup-prod)'],
    ['gcp', 'backup-prod', 'GCS(backup-prod)'],
  ])('uses the platform prefix for %s', (platform, bucket, expected) => {
    expect(buildS3RepositoryName(platform, bucket)).toBe(expected)
  })

  it('returns the platform abbreviation until a bucket is available', () => {
    expect(buildS3RepositoryName('other', '  ')).toBe('S3')
    expect(buildS3RepositoryName('aliyun', '')).toBe('OSS')
  })

  it('returns an empty name when the platform is unavailable', () => {
    expect(buildS3RepositoryName(undefined, 'backup-prod')).toBe('')
    expect(buildS3RepositoryName('unknown', 'backup-prod')).toBe('')
  })
})
