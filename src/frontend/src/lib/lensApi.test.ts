// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import {
  setLensApiScope,
  setLensDefaultAgentModel,
  setLensDefaultMultimodalModel,
  testSavedLensModel,
} from './lensApi'

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

describe('AI model role defaults', () => {
  it('updates the tenant Agent default through org settings', async () => {
    vi.mocked(api).mockResolvedValue({
      default_agent_model_ref: 'agent-uuid',
      default_multimodal_model_ref: null,
    })

    await setLensDefaultAgentModel('agent-uuid')

    expect(api).toHaveBeenCalledWith(
      '/api/v1/lens/settings/',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ default_agent_model_ref: 'agent-uuid' }),
      }),
    )
  })

  it('updates the platform multimodal default through Admin Console settings', async () => {
    setLensApiScope('platform')
    vi.mocked(api).mockResolvedValue({
      default_agent_model_ref: null,
      default_multimodal_model_ref: 'multimodal-uuid',
    })

    await setLensDefaultMultimodalModel('multimodal-uuid')

    expect(api).toHaveBeenCalledWith(
      '/api/v1/platform-ops/lens/settings',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          default_multimodal_model_ref: 'multimodal-uuid',
        }),
      }),
    )
  })
})
