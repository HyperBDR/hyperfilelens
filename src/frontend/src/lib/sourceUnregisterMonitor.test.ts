import { describe, expect, it } from 'vitest'

import {
  sourceUnregisterTaskBindings,
  sourceUnregisterTaskOutcome,
} from './sourceUnregisterMonitor'

describe('sourceUnregisterTaskBindings', () => {
  it('uses the explicit source-to-task mapping instead of array position', () => {
    expect(sourceUnregisterTaskBindings(['agent:1', 'nas:2'], {
      tasks: [
        { source_id: 'nas:2', task_id: 22, task_uuid: 'task-nas' },
        { source_id: 'agent:1', task_id: 11, task_uuid: 'task-agent' },
      ],
    })).toEqual([
      { sourceId: 'nas:2', taskId: 22, taskUuid: 'task-nas' },
      { sourceId: 'agent:1', taskId: 11, taskUuid: 'task-agent' },
    ])
  })

  it('keeps compatibility with the legacy parallel arrays', () => {
    expect(sourceUnregisterTaskBindings(['agent:1'], {
      task_ids: [11],
      task_uuids: ['task-agent'],
    })).toEqual([{ sourceId: 'agent:1', taskId: 11, taskUuid: 'task-agent' }])
  })
})

describe('sourceUnregisterTaskOutcome', () => {
  it('exposes terminal failure details immediately', () => {
    expect(sourceUnregisterTaskOutcome({
      status: 'failed',
      error_message: 'Agent uninstall callback failed',
      result_payload: {},
    } as never)).toMatchObject({
      terminal: true,
      success: false,
      errorMessage: 'Agent uninstall callback failed',
    })
  })

  it('distinguishes force cleanup residue from a clean success', () => {
    expect(sourceUnregisterTaskOutcome({
      status: 'success',
      result_payload: {
        result: 'partial_success',
        cleanup_complete: false,
        retained_resources: ['agent_installation'],
      },
    } as never)).toMatchObject({
      terminal: true,
      success: true,
      partialSuccess: true,
      cleanupComplete: false,
    })

    expect(sourceUnregisterTaskOutcome({
      status: 'success',
      result_payload: {
        result: 'success',
        cleanup_complete: true,
      },
    } as never)).toMatchObject({
      success: true,
      partialSuccess: false,
      cleanupComplete: true,
    })
  })
})
