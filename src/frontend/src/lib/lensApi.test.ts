// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import { setLensApiScope, testSavedLensModel } from './lensApi'

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()
  return {
    ...actual,
    api: vi.fn(),
  }
})

vi.mock('../composables/useAuth', () => ({
  getEffectiveOrgKey: vi.fn(() => 'tenant-a'),
}))

afterEach(() => {
  setLensApiScope('tenant')
  vi.clearAllMocks()
})

describe('saved AI model connectivity', () => {
  it('uses the Admin Console test-call route without sending credentials', async () => {
    setLensApiScope('platform')
    vi.mocked(api).mockResolvedValue({ ok: true })

    await testSavedLensModel('model-uuid')

    expect(api).toHaveBeenCalledWith(
      '/api/v1/platform-ops/lens/models/model-uuid/test-call',
      expect.objectContaining({
        method: 'POST',
        body: '{}',
      }),
    )
  })
})
