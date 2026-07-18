import { describe, expect, it } from 'vitest'

import type { BackupSourceDirectoryEntry } from './sourceApi'
import {
  selectBackupSourceDirectoryTreeEntries,
  shouldAutoExpandRefreshedDirectory,
} from './backupSourceDirectoryTree'

const root: BackupSourceDirectoryEntry = {
  label: '/',
  path: '/',
  isLeaf: false,
  is_dir: true,
  path_type: 'directory',
}

const boot: BackupSourceDirectoryEntry = {
  label: 'boot',
  path: '/boot',
  isLeaf: false,
  is_dir: true,
  path_type: 'directory',
}

const windowsDrives: BackupSourceDirectoryEntry[] = [
  { label: 'C:\\', path: 'C:\\', isLeaf: false, is_dir: true, path_type: 'directory' },
  { label: 'D:\\', path: 'D:\\', isLeaf: false, is_dir: true, path_type: 'directory' },
]

describe('selectBackupSourceDirectoryTreeEntries', () => {
  it.each(['linux', 'macos'] as const)('uses a single root for %s hosts', (platform) => {
    expect(selectBackupSourceDirectoryTreeEntries({
      source: { type: 'host', platform },
      parentPath: '',
      result: { root, entries: [root, boot] },
    })).toEqual([root])
  })

  it('uses a single share root for NAS sources', () => {
    expect(selectBackupSourceDirectoryTreeEntries({
      source: { type: 'nas' },
      parentPath: '',
      result: { root, entries: [root, boot] },
    })).toEqual([root])
  })

  it('keeps Windows drive roots', () => {
    expect(selectBackupSourceDirectoryTreeEntries({
      source: { type: 'host', platform: 'windows' },
      parentPath: '',
      result: { root: windowsDrives[0], entries: windowsDrives },
    })).toEqual(windowsDrives)
  })

  it('returns directory children after a POSIX root is expanded', () => {
    expect(selectBackupSourceDirectoryTreeEntries({
      source: { type: 'host', platform: 'linux' },
      parentPath: '/',
      result: { root, entries: [boot] },
    })).toEqual([boot])
  })
})

describe('shouldAutoExpandRefreshedDirectory', () => {
  it('expands a previously collapsed directory after a non-empty refresh', () => {
    expect(shouldAutoExpandRefreshedDirectory({
      wasExpanded: false,
      hasChildren: true,
      expansionRevisionAtStart: 2,
      expansionRevisionAfterRefresh: 2,
    })).toBe(true)
  })

  it('keeps an already expanded directory unchanged', () => {
    expect(shouldAutoExpandRefreshedDirectory({
      wasExpanded: true,
      hasChildren: true,
      expansionRevisionAtStart: 2,
      expansionRevisionAfterRefresh: 2,
    })).toBe(false)
  })

  it('does not expand an empty directory', () => {
    expect(shouldAutoExpandRefreshedDirectory({
      wasExpanded: false,
      hasChildren: false,
      expansionRevisionAtStart: 2,
      expansionRevisionAfterRefresh: 2,
    })).toBe(false)
  })

  it('respects expansion changes made while the refresh is in progress', () => {
    expect(shouldAutoExpandRefreshedDirectory({
      wasExpanded: false,
      hasChildren: true,
      expansionRevisionAtStart: 2,
      expansionRevisionAfterRefresh: 3,
    })).toBe(false)
  })
})
