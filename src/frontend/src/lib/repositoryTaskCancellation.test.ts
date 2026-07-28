import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  canCancelRepositoryTask,
  createRepositoryTaskCancellationPoller,
  isRepositoryTaskCancellationPending,
} from './repositoryTaskCancellation'
import type { TaskRow } from './taskApi'

function task(overrides: Partial<TaskRow> = {}): TaskRow {
  return {
    id: 1,
    organization_id: 1,
    task_uuid: 'task-1',
    task_type: 'repository_operation',
    display_name: 'Quick maintenance',
    status: 'running',
    progress: 25,
    retry_count: 0,
    recovery_attempt: 0,
    trigger_type: 'system',
    repository_cancellation: { supported: true, requested_at: null },
    ...overrides,
  }
}

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('repository task cancellation policy', () => {
  it('allows only active controller maintenance exposed as cancellable by the API', () => {
    expect(canCancelRepositoryTask(task())).toBe(true)
    expect(canCancelRepositoryTask(task({ status: 'success' }))).toBe(false)
    expect(canCancelRepositoryTask(task({ repository_cancellation: { supported: false } }))).toBe(false)
    expect(canCancelRepositoryTask(task({
      operation_type: 'cleanup.repository',
      repository_cancellation: { supported: false },
    }))).toBe(false)
  })

  it('keeps a requested running cancellation visible as pending', () => {
    expect(isRepositoryTaskCancellationPending(task({
      repository_cancellation: {
        supported: true,
        requested_at: '2026-07-24T04:00:00Z',
      },
    }))).toBe(true)
  })
})

describe('repository task cancellation polling', () => {
  it('polls every two seconds and stops after a terminal update', async () => {
    vi.useFakeTimers()
    const fetchTask = vi.fn()
      .mockResolvedValueOnce(task())
      .mockResolvedValueOnce(task({ status: 'cancelled' }))
    const onUpdate = vi.fn()
    const poller = createRepositoryTaskCancellationPoller({ fetchTask, onUpdate })

    poller.start('task-1')
    await vi.advanceTimersByTimeAsync(2000)
    await vi.advanceTimersByTimeAsync(2000)
    await vi.advanceTimersByTimeAsync(4000)

    expect(fetchTask).toHaveBeenCalledTimes(2)
    expect(onUpdate).toHaveBeenCalledTimes(2)
    expect(onUpdate.mock.calls[1][0].status).toBe('cancelled')
  })

  it('stops polling when its owner closes', async () => {
    vi.useFakeTimers()
    const fetchTask = vi.fn().mockResolvedValue(task())
    const poller = createRepositoryTaskCancellationPoller({
      fetchTask,
      onUpdate: vi.fn(),
    })

    poller.start('task-1')
    poller.stop()
    await vi.advanceTimersByTimeAsync(4000)

    expect(fetchTask).not.toHaveBeenCalled()
  })
})
