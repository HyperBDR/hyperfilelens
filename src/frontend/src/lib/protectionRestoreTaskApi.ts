import { api } from './api'
import { unwrapApiPayload } from './parse'

export type RestoreTaskActionResult = {
  task_uuid: string
  status: string
  restore_record_id?: number | null
}

const restoreTaskBase = '/api/v1/restore/tasks'

export async function cancelProtectionRestoreTask(taskUuid: string, reason?: string) {
  return unwrapApiPayload<RestoreTaskActionResult>(
    await api<unknown>(`${restoreTaskBase}/${taskUuid}/cancel/`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || '' }),
    }),
  )
}
