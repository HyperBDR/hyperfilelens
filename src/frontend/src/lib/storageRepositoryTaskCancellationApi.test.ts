// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { getEffectiveOrgKey } from '../composables/useAuth'
import { api } from './api'
import { cancelStorageRepositoryTask } from './storageRepositoryApi'

vi.mock('../composables/useAuth', () => ({
  getEffectiveOrgKey: vi.fn(() => 'org-demo'),
}))

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()
  return { ...actual, api: vi.fn() }
})

afterEach(() => vi.clearAllMocks())

describe('storage repository task cancellation API', () => {
  it('uses the dedicated storage endpoint and organization scope', async () => {
    vi.mocked(api).mockResolvedValue({ task_uuid: 'task-1', status: 'running' })

    await cancelStorageRepositoryTask('task-1', 'cancel this run')

    expect(getEffectiveOrgKey).toHaveBeenCalled()
    expect(api).toHaveBeenCalledWith(
      '/api/v1/storage/repository-tasks/task-1/cancel/',
      {
        method: 'POST',
        body: JSON.stringify({ reason: 'cancel this run' }),
        headers: { 'X-Org-Key': 'org-demo' },
      },
    )
  })
})
