import type { BackupSourceDeleteResult } from './sourceApi'
import type { TaskRow } from './taskApi'

export type SourceUnregisterTaskBinding = {
  sourceId: string
  taskId?: number
  taskUuid: string
}

export function sourceUnregisterTaskBindings(
  sourceIds: string[],
  result: Pick<BackupSourceDeleteResult, 'tasks' | 'task_id' | 'task_uuid' | 'task_ids' | 'task_uuids'>,
): SourceUnregisterTaskBinding[] {
  if (result.tasks?.length) {
    return result.tasks.flatMap((task) =>
      task.source_id && task.task_uuid
        ? [{ sourceId: task.source_id, taskId: task.task_id, taskUuid: task.task_uuid }]
        : [],
    )
  }
  const taskIds = result.task_ids?.length ? result.task_ids : [result.task_id]
  const taskUuids = result.task_uuids?.length ? result.task_uuids : [result.task_uuid]
  return sourceIds.flatMap((sourceId, index) => {
    const taskUuid = taskUuids[index] || ''
    return taskUuid ? [{ sourceId, taskId: taskIds[index], taskUuid }] : []
  })
}

export function sourceUnregisterTaskOutcome(task: TaskRow) {
  const status = String(task.status || '').toLowerCase()
  const terminal = ['success', 'failed', 'cancelled', 'timeout'].includes(status)
  const payload = task.result_payload && typeof task.result_payload === 'object'
    ? task.result_payload as Record<string, unknown>
    : {}
  const rawRemovals = Array.isArray(payload.pending_removals) ? payload.pending_removals : []
  const result = String(payload.result || '').toLowerCase()
  const cleanupComplete = payload.cleanup_complete !== false
  const pendingRemovals = rawRemovals.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const sourceId = String(row.source_id || '')
    const nodeId = Number(row.node_id || 0)
    return sourceId && nodeId > 0 ? [{ source_id: sourceId, node_id: nodeId }] : []
  })
  return {
    terminal,
    success: status === 'success',
    partialSuccess: status === 'success' && (result === 'partial_success' || !cleanupComplete),
    cleanupComplete,
    status,
    pendingRemovals,
    errorMessage: String(task.error_message || task.error_code || '').trim(),
  }
}
