import type { TaskResourceRow, TaskRow } from './taskApi'

type JsonRecord = Record<string, unknown>

export type TaskCleanupFailure = {
  code: string
  detail: string
  sourceId?: string
  sourceName?: string
}

function record(value: unknown): JsonRecord {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : {}
}

function records(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? value.filter((item): item is JsonRecord => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : []
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map(item => String(item || '').trim()).filter(Boolean)
    : []
}

function cleanupItem(value: JsonRecord, fallbackCode: string, fallbackDetail: string): TaskCleanupFailure {
  return {
    code: String(value.code || fallbackCode).trim(),
    detail: String(value.detail || fallbackDetail).trim(),
    sourceId: String(value.source_id || '').trim() || undefined,
    sourceName: String(value.source_name || '').trim() || undefined,
  }
}

function cleanupCore(item: TaskCleanupFailure) {
  return `${item.code.toLowerCase()}\u0000${item.detail.replace(/\s+/g, ' ')}`
}

function dedupeCleanupItems(items: TaskCleanupFailure[]): TaskCleanupFailure[] {
  const merged: TaskCleanupFailure[] = []
  for (const item of items) {
    const core = cleanupCore(item)
    const existingIndex = merged.findIndex(existing => (
      cleanupCore(existing) === core
      && (!item.sourceId || !existing.sourceId || item.sourceId === existing.sourceId)
    ))
    if (existingIndex < 0) {
      merged.push(item)
    } else if (item.sourceId && !merged[existingIndex].sourceId) {
      merged[existingIndex] = item
    }
  }
  return merged
}

export function taskResultRecord(task?: TaskRow | null): JsonRecord {
  return record(task?.result_payload)
}

export function taskDisplayStatus(task?: TaskRow | null) {
  const status = String(task?.status || '').trim().toLowerCase()
  const result = taskResultRecord(task)
  const outcome = String(result.result || result.outcome || '').trim().toLowerCase()
  if (status === 'success' && (
    outcome === 'partial_success'
    || result.cleanup_complete === false
  )) return 'partial'
  return status
}

export function taskCleanupFailures(task?: TaskRow | null): TaskCleanupFailure[] {
  const result = taskResultRecord(task)
  return dedupeCleanupItems(
    records(result.cleanup_failures).map(item => cleanupItem(item, 'cleanup_failed', 'Cleanup failed.')),
  )
}

export function taskRetainedResources(task?: TaskRow | null): string[] {
  return [...new Set(strings(taskResultRecord(task).retained_resources))]
}

export function taskCleanupWarnings(task?: TaskRow | null): TaskCleanupFailure[] {
  const result = taskResultRecord(task)
  const failures = taskCleanupFailures(task)
  return dedupeCleanupItems(
    records(result.warnings).map(item => cleanupItem(item, 'cleanup_warning', 'Cleanup completed with a warning.')),
  ).filter(warning => !failures.some(failure => (
    cleanupCore(failure) === cleanupCore(warning)
    && (!warning.sourceId || !failure.sourceId || warning.sourceId === failure.sourceId)
  )))
}

export function taskFailedCleanupChildren(task?: TaskRow | null): Array<{ taskUuid: string; error: string }> {
  const result = taskResultRecord(task)
  const children = [
    ...records(result.repository_cleanup_tasks),
    ...records(result.snapshot_cleanup_tasks),
  ]
  const seen = new Set<string>()
  return children.flatMap((item) => {
    const status = String(item.status || '').toLowerCase()
    const taskUuid = String(item.task_uuid || '').trim()
    if (!taskUuid || !['failed', 'timeout', 'cancelled', 'canceled'].includes(status) || seen.has(taskUuid)) return []
    seen.add(taskUuid)
    return [{
      taskUuid,
      error: String(item.error_message || item.error_code || status).trim(),
    }]
  })
}

export function taskNeedsManualCleanup(task?: TaskRow | null) {
  return [
    ...taskCleanupFailures(task).map(item => item.code),
    ...taskCleanupWarnings(task).map(item => item.code),
  ].some(code => ['repository_cleanup_required', 'repository_purge_pending'].includes(code))
    || taskRetainedResources(task).some(item => item.startsWith('repository_cleanup_record:') || item.startsWith('repository_purge_pending:'))
}

export function taskResourceSnapshot(task: TaskRow | null | undefined, resource: TaskResourceRow): JsonRecord | null {
  const request = record(task?.request_payload)
  const result = taskResultRecord(task)
  if (resource.resource_type === 'backup_source') {
    const source = record(record(request.cleanup_plan).source)
    if (Object.keys(source).length) {
      const config = record(source.config)
      const endpoint = source.endpoint
        || config.server
        || config.host
        || config.smb_server
        || config.nfs_host
      return {
        id: resource.resource_id,
        name: source.name,
        resource_type: source.kind || resource.resource_subtype,
        endpoint,
        ip_address: endpoint,
        created_at: source.registered_at,
        mount_point: source.mount_point,
        config: source.config,
      }
    }
    // Fallback: source_orphan_display_name (available on source_unregister tasks)
    const orphanName = typeof request.source_orphan_display_name === 'string'
      ? request.source_orphan_display_name.trim()
      : ''
    if (orphanName) {
      return {
        id: resource.resource_id,
        name: orphanName,
        resource_type: resource.resource_subtype || 'agent',
        created_at: '',
      }
    }
    // Fallback: result_payload.sources[].source_name
    const sources = Array.isArray(result.sources) ? result.sources : []
    const matchedSource = sources.find(
      (s: unknown) => s && typeof s === 'object' && (s as JsonRecord).source_name,
    ) as JsonRecord | undefined
    if (matchedSource?.source_name) {
      return {
        id: resource.resource_id,
        name: String(matchedSource.source_name),
        resource_type: resource.resource_subtype || 'agent',
        created_at: '',
      }
    }
  }
  if (resource.resource_type === 'repository' || resource.resource_type === 'target_repository') {
    const repository = record(record(request.cleanup_plan).repository)
    if (Object.keys(repository).length) {
      return {
        ...repository,
        id: resource.resource_id,
        repo_type: repository.type,
      }
    }
  }
  if (resource.resource_type === 'host') {
    const node = record(request.node)
    const fallback = Object.keys(node).length ? node : record(result.node)
    if (Object.keys(fallback).length) {
      return {
        ...fallback,
        id: resource.resource_id,
        ip_address: fallback.endpoint,
        created_at: fallback.registered_at,
      }
    }
  }
  return null
}
