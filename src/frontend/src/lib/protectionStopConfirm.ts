import type { TaskRow } from './taskApi'
import { formatTaskProgressPercent } from './kopiaProgress'

export type ProtectionStopConfirmItem = {
  name: string
  description?: string
  /** Progress text, target path, hostname, or other detail line */
  hint?: string
}

export function restoreTargetPathFromTask(task: TaskRow): string {
  const payload = task.request_payload
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return ''
  return String((payload as Record<string, unknown>).target_path || '').trim()
}

export function buildStopConfirmItemFromTask(task: TaskRow): ProtectionStopConfirmItem {
  const progress = formatTaskProgressPercent(task.progress)
  if (task.task_type === 'restore') {
    const target = restoreTargetPathFromTask(task)
    return {
      name: task.display_name || task.task_uuid,
      hint: target || undefined,
      description: progress,
    }
  }
  return {
    name: task.display_name || task.task_uuid,
    description: progress,
  }
}
