import { describe, expect, it } from 'vitest'

import { restoreDirectoryBrowseSourceId } from './restoreDirectoryTarget'

describe('restoreDirectoryBrowseSourceId', () => {
  it('preserves the NAS resource identity for mounted directory browsing', () => {
    expect(restoreDirectoryBrowseSourceId('nas:0012')).toBe('nas:12')
  })

  it('preserves agent destinations and unknown legacy values', () => {
    expect(restoreDirectoryBrowseSourceId('agent:8')).toBe('agent:8')
    expect(restoreDirectoryBrowseSourceId('proxy-directory')).toBe('proxy-directory')
  })
})
