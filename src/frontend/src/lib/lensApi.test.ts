// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import type { LensIngestPolicy } from './lensApi'
import {
  createKnowledgeSource,
  patchKnowledgeSource,
  setLensApiScope,
  setLensDefaultAgentModel,
  setLensDefaultMultimodalModel,
  testSavedLensModel,
} from './lensApi'

const ingestPolicy: LensIngestPolicy = {
  document: true,
  embedded_image: true,
  image: true,
  document_model_ref: 'document-model',
  vision_model_ref: 'vision-model',
  max_images: 20,
  max_file_size_mb: 100,
  max_pages: 200,
  pdf_extract_images: true,
  pdf_extract_images_on_text_pages: false,
  pdf_render_scanned_pages: true,
  pdf_max_pages: 200,
  pdf_max_images_per_page: 10,
  pdf_render_dpi: 144,
  pdf_min_text_chars: 80,
  pdf_min_image_area_ratio: 0.1,
}

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

describe('knowledge source ingest policy', () => {
  it.each([
    ['create', () => createKnowledgeSource({
      name: 'Documents',
      gateway: 42,
      source_path: '/documents',
      ingest_policy: ingestPolicy,
    })],
    ['patch', () => patchKnowledgeSource(7, { ingest_policy: ingestPolicy })],
  ])('keeps deployment-owned model references out of %s requests', async (_operation, request) => {
    vi.mocked(api).mockResolvedValue({ id: 7 })

    await request()

    const options = vi.mocked(api).mock.calls[0]?.[1]
    const body = JSON.parse(String(options?.body))
    expect(body.ingest_policy).not.toHaveProperty('document_model_ref')
    expect(body.ingest_policy).not.toHaveProperty('vision_model_ref')
    expect(body.ingest_policy.document).toBe(true)
    expect(ingestPolicy.document_model_ref).toBe('document-model')
    expect(ingestPolicy.vision_model_ref).toBe('vision-model')
  })
})
