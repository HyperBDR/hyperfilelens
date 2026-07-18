// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, apiErrorMessage, apiErrorMessageI18n } from './api'
import { getRouteRequestSignal } from './routeRequestAbort'

vi.mock('./routeRequestAbort', () => ({
  getRouteRequestSignal: vi.fn(),
}))

const routeSignal = new AbortController().signal

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('api request cancellation', () => {
  it('keeps a caller-provided signal independent from route query changes', async () => {
    const requestController = new AbortController()
    vi.mocked(getRouteRequestSignal).mockReturnValue(routeSignal)
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await api('/api/v1/source/backup-selectable/', { signal: requestController.signal })

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[0][1]?.signal).toBe(requestController.signal)
  })

  it('uses the route signal when the caller does not provide one', async () => {
    vi.mocked(getRouteRequestSignal).mockReturnValue(routeSignal)
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await api('/api/v1/source/backup-selectable/')

    expect(fetchMock.mock.calls[0][1]?.signal).toBe(routeSignal)
  })
})

describe('api validation errors', () => {
  it('shows the backend field message instead of the generic validation message', async () => {
    vi.mocked(getRouteRequestSignal).mockReturnValue(routeSignal)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      code: 400,
      message: 'failed',
      data: {
        title: 'Validation failed',
        status: 400,
        code: 'VALIDATION.FAILED',
        errors: [{
          field: 'model',
          code: 'VALIDATION.FIELD_INVALID',
          message: 'Configure an active AI model before creating a chat.',
        }],
      },
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })))

    let message = ''
    try {
      await api('/api/v1/lens/copilot/sessions/', { method: 'POST' })
    } catch (error) {
      message = apiErrorMessage(error)
    }

    expect(message).toBe('Configure an active AI model before creating a chat.')
  })
})

describe('repository conflict errors', () => {
  it('maps an existing repository conflict to localized copy', () => {
    const message = apiErrorMessageI18n(
      {
        status: 409,
        message: 'Repository already exists',
        errorCode: 'STORAGE.REPOSITORY_ALREADY_EXISTS',
      },
      (key) => key === 'errors.codes.storageRepositoryAlreadyExists'
        ? 'A Kopia repository already exists at the selected location. Import is not supported in this version. Choose a different storage location.'
        : key,
    )

    expect(message).toBe('A Kopia repository already exists at the selected location. Import is not supported in this version. Choose a different storage location.')
  })
})
