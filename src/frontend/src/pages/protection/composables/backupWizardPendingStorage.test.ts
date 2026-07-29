// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest'
import {
  markWizardPendingBySourceIds,
  readWizardPendingSourceOps,
  WIZARD_PENDING_STORAGE_KEY,
} from './backupWizardPendingStorage'

describe('backup wizard pending source storage', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it('persists the parent unregister task needed to resume reconciliation', () => {
    markWizardPendingBySourceIds(['nas:42'], {
      kind: 'deleting',
      taskId: 17,
      taskUuid: 'task-uuid-17',
      startedAt: 1234,
    })

    expect(readWizardPendingSourceOps().get('nas:42')).toEqual({
      kind: 'deleting',
      taskId: 17,
      taskUuid: 'task-uuid-17',
      startedAt: 1234,
    })
    expect(window.sessionStorage.getItem(WIZARD_PENDING_STORAGE_KEY)).toContain('task-uuid-17')
  })

  it('allows a terminal asynchronous failure to replace deleting state', () => {
    markWizardPendingBySourceIds(['agent:9'], {
      kind: 'deleting',
      taskUuid: 'task-uuid-9',
    })
    markWizardPendingBySourceIds(['agent:9'], {
      kind: 'delete_failed',
      taskUuid: 'task-uuid-9',
    })

    expect(readWizardPendingSourceOps().get('agent:9')?.kind).toBe('delete_failed')
  })
})
