import { describe, expect, it } from 'vitest'
import type { TaskRow } from './taskApi'
import {
  taskCleanupFailures,
  taskDisplayStatus,
  taskNeedsManualCleanup,
  taskResourceSnapshot,
} from './taskOutcomeDisplay'

function task(overrides: Partial<TaskRow>): TaskRow {
  return {
    id: 1,
    organization_id: 1,
    task_uuid: 'task-1',
    task_type: 'source_unregister',
    display_name: 'Unregister source',
    status: 'success',
    progress: 100,
    retry_count: 0,
    recovery_attempt: 0,
    trigger_type: 'manual',
    ...overrides,
  }
}

describe('taskOutcomeDisplay', () => {
  it('shows successful force residue as partial', () => {
    expect(taskDisplayStatus(task({ result_payload: { result: 'partial_success', cleanup_complete: false } }))).toBe('partial')
  })

  it('deduplicates identical cleanup failures', () => {
    const row = task({
      result_payload: {
        cleanup_failures: [
          { code: 'agent_offline', detail: 'Agent is offline' },
          { source_id: 'agent:1', code: 'agent_offline', detail: 'Agent  is offline' },
        ],
      },
    })
    expect(taskCleanupFailures(row)).toHaveLength(1)
    expect(taskCleanupFailures(row)[0].sourceId).toBe('agent:1')
  })

  it('recognizes legacy and current manual repository residue', () => {
    expect(taskNeedsManualCleanup(task({ result_payload: { retained_resources: ['repository_purge_pending:2'] } }))).toBe(true)
    expect(taskNeedsManualCleanup(task({ result_payload: { retained_resources: ['repository_cleanup_record:3'] } }))).toBe(true)
  })

  it('uses the immutable source cleanup plan after live deletion', () => {
    const row = task({
      request_payload: {
        cleanup_plan: {
          source: { name: 'host-a', kind: 'agent', endpoint: '10.0.0.8', registered_at: '2026-01-01T00:00:00Z' },
        },
      },
    })
    expect(taskResourceSnapshot(row, { resource_type: 'backup_source', resource_subtype: 'agent', resource_id: 8 })).toMatchObject({
      name: 'host-a',
      ip_address: '10.0.0.8',
    })
  })
})
