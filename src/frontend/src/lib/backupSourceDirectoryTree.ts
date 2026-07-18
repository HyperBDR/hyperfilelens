import type {
  BackupSelectableSource,
  BackupSourceDirectoryEntry,
  BackupSourceDirectoryList,
} from './sourceApi'

export type BackupSourceDirectoryTreeSource = Pick<BackupSelectableSource, 'type' | 'platform'>

export function shouldUseSingleDirectoryRoot(
  source: BackupSourceDirectoryTreeSource | null | undefined,
  parentPath: string,
) {
  if (parentPath || !source) return false
  if (source.type === 'nas') return true
  return source.type === 'host' && (source.platform === 'linux' || source.platform === 'macos')
}

export function selectBackupSourceDirectoryTreeEntries(params: {
  source: BackupSourceDirectoryTreeSource | null | undefined
  parentPath: string
  result: Pick<BackupSourceDirectoryList, 'root' | 'entries'>
}): BackupSourceDirectoryEntry[] {
  const { source, parentPath, result } = params
  if (shouldUseSingleDirectoryRoot(source, parentPath)) {
    return result.root ? [result.root] : []
  }
  if (result.entries.length > 0) return result.entries
  return !parentPath && result.root ? [result.root] : []
}

export function shouldAutoExpandRefreshedDirectory(params: {
  wasExpanded: boolean
  hasChildren: boolean
  expansionRevisionAtStart: number
  expansionRevisionAfterRefresh: number
}) {
  return !params.wasExpanded
    && params.hasChildren
    && params.expansionRevisionAtStart === params.expansionRevisionAfterRefresh
}
