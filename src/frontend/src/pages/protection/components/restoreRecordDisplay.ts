import type { RestoreRecord, RestoreRecordItem } from '../../../lib/restoreApi'

export type RestoreRecordPathMapping = {
  key: string
  item: RestoreRecordItem
  sourcePath: string
  sourceKind: 'file' | 'dir'
}

export function restoreRecordTaskStatus(record: RestoreRecord) {
  return String(record.task_summary?.status || '').trim().toLowerCase()
}

export function shouldShowRestoreRecordProgress(record: RestoreRecord) {
  return restoreRecordTaskStatus(record) === 'running'
}

export function restoreRecordSnapshotLabel(record: RestoreRecord) {
  return String(record.source_snapshot_uid || '').trim() || `#${record.source_snapshot_id}`
}

export function joinRestoreRecordSourcePath(basePath: string, selectedPath: string) {
  const base = String(basePath || '').trim()
  const selected = String(selectedPath || '').trim()
  if (!selected) return base || '—'
  if (/^(?:[A-Za-z]:[\\/]|[\\/]{1,2})/.test(selected)) return selected
  if (!base) return selected
  const separator = base.includes('\\') ? '\\' : '/'
  const normalizedBase = base.replace(/[\\/]+$/, '')
  const normalizedSelected = selected.replace(/^[\\/]+/, '')
  return `${normalizedBase}${separator}${normalizedSelected}`
}

function restoreRecordPathKind(path: string): 'file' | 'dir' {
  const base = path.split(/[\\/]/).filter(Boolean).pop() || ''
  return /\.[A-Za-z0-9]{1,16}$/.test(base) ? 'file' : 'dir'
}

export function restoreRecordPathMappings(record: RestoreRecord): RestoreRecordPathMapping[] {
  return record.items.flatMap((item) => {
    const selectedPaths = Array.isArray(item.selected_paths)
      ? item.selected_paths.map((path) => String(path || '').trim()).filter(Boolean)
      : []
    const paths = selectedPaths.length
      ? selectedPaths.map((path) => joinRestoreRecordSourcePath(item.source_path, path))
      : [item.source_path || '—']
    return paths.map((sourcePath, index) => ({
      key: `${item.id}:${index}:${sourcePath}`,
      item,
      sourcePath,
      sourceKind: restoreRecordPathKind(sourcePath),
    }))
  })
}
