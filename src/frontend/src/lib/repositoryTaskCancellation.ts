import type { TaskRow } from './taskApi'

const ACTIVE_TASK_STATUSES = new Set(['pending', 'running'])
const TERMINAL_TASK_STATUSES = new Set(['success', 'failed', 'cancelled', 'timeout'])

export function isRepositoryTaskCancellationSupported(task?: TaskRow | null): boolean {
  return Boolean(
    task
    && task.task_type === 'repository_operation'
    && task.repository_cancellation?.supported === true,
  )
}

export function canCancelRepositoryTask(task?: TaskRow | null): boolean {
  return Boolean(
    task
    && ACTIVE_TASK_STATUSES.has(task.status)
    && isRepositoryTaskCancellationSupported(task),
  )
}

export function isRepositoryTaskCancellationPending(task?: TaskRow | null): boolean {
  return Boolean(
    task
    && ACTIVE_TASK_STATUSES.has(task.status)
    && task.repository_cancellation?.requested_at,
  )
}

export function isTerminalTaskStatus(status?: string | null): boolean {
  return TERMINAL_TASK_STATUSES.has(String(status || ''))
}

type RepositoryTaskCancellationPollerOptions = {
  fetchTask: (taskUuid: string) => Promise<TaskRow>
  onUpdate: (task: TaskRow) => void | Promise<void>
  onError?: (error: unknown) => void
  intervalMs?: number
}

export function createRepositoryTaskCancellationPoller(
  options: RepositoryTaskCancellationPollerOptions,
) {
  const intervalMs = options.intervalMs ?? 2000
  let timer: ReturnType<typeof setTimeout> | undefined
  let generation = 0
  let errorReported = false

  function stop() {
    generation += 1
    if (timer) clearTimeout(timer)
    timer = undefined
    errorReported = false
  }

  function schedule(taskUuid: string, activeGeneration: number) {
    timer = setTimeout(() => void poll(taskUuid, activeGeneration), intervalMs)
  }

  async function poll(taskUuid: string, activeGeneration: number) {
    try {
      const task = await options.fetchTask(taskUuid)
      if (activeGeneration !== generation) return
      errorReported = false
      await options.onUpdate(task)
      if (activeGeneration !== generation || isTerminalTaskStatus(task.status)) return
    } catch (error) {
      if (activeGeneration !== generation) return
      if (!errorReported) options.onError?.(error)
      errorReported = true
    }
    if (activeGeneration === generation) schedule(taskUuid, activeGeneration)
  }

  function start(taskUuid: string) {
    stop()
    const activeGeneration = generation
    schedule(taskUuid, activeGeneration)
  }

  return { start, stop }
}
