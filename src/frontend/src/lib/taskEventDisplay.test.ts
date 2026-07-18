import { describe, expect, it } from 'vitest'
import { en } from '../locales/en'
import { parseTaskStepStatusEvent, taskEventMessageKey } from './taskEventDisplay'

describe('task event internationalization', () => {
  it('covers every repository cleanup step exposed by the backend', () => {
    const cleanupSteps = [
      'cleanup_direct_nas_repositories',
      'check_cleanup_dependencies',
      'verify_cleanup_owner',
      'prepare_cleanup_target',
      'delete_physical_repository',
      'cleanup_owner_local_state',
      'verify_cleanup_result',
      'finalize_cleanup_metadata',
    ]
    const translations = en.ops.task.step as Record<string, string>

    for (const step of cleanupSteps) expect(translations[step]).toBeTruthy()
  })

  it('maps Direct NAS cleanup event messages to translation keys', () => {
    expect(taskEventMessageKey('Cleaning Direct NAS physical repositories'))
      .toBe('ops.task.eventMessage.cleaningDirectNasPhysicalRepositories')
    expect(taskEventMessageKey('Direct NAS repository cleanup completed'))
      .toBe('ops.task.eventMessage.directNasRepositoryCleanupCompleted')
  })

  it('normalizes known messages and preserves unknown messages for callers', () => {
    expect(taskEventMessageKey('  TASK STARTED  ')).toBe('ops.task.eventMessage.taskStarted')
    expect(taskEventMessageKey('Task finished after worker reconciliation'))
      .toBe('ops.task.eventMessage.taskFinished')
    expect(taskEventMessageKey('Repository cleanup failed: permission denied')).toBeNull()
  })

  it('parses repository step status events', () => {
    expect(parseTaskStepStatusEvent('Step delete_physical_repository running')).toEqual({
      step: 'delete_physical_repository',
      status: 'running',
    })
    expect(parseTaskStepStatusEvent('Physical repository deleted')).toBeNull()
  })
})
