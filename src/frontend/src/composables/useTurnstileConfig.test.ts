// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  preloadTurnstileScript: vi.fn(),
  resetTurnstileScriptLoad: vi.fn(),
}))

vi.mock('../lib/api', () => ({ api: mocks.api }))
vi.mock('../lib/turnstileLoader', () => ({
  preloadTurnstileScript: mocks.preloadTurnstileScript,
  resetTurnstileScriptLoad: mocks.resetTurnstileScriptLoad,
}))

describe('Turnstile configuration retry', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    mocks.preloadTurnstileScript.mockResolvedValue(undefined)
  })

  it('clears the shared loader and recovers after a configuration failure', async () => {
    mocks.api
      .mockRejectedValueOnce(new Error('network unavailable'))
      .mockResolvedValueOnce({
        code: '0000',
        data: {
          enabled: true,
          configured: true,
          site_key: 'test-site-key',
        },
      })

    const { useTurnstileConfig } = await import('./useTurnstileConfig')
    const turnstile = useTurnstileConfig()

    await turnstile.loadTurnstileConfig()
    expect(turnstile.isTurnstileBlocked.value).toBe(true)

    await Promise.all([
      turnstile.retryTurnstileConfig(),
      turnstile.retryTurnstileConfig(),
    ])

    expect(mocks.resetTurnstileScriptLoad).toHaveBeenCalledTimes(1)
    expect(turnstile.authTurnstileMountGeneration.value).toBe(1)
    expect(turnstile.isTurnstileReady.value).toBe(true)
    expect(turnstile.turnstileSiteKey.value).toBe('test-site-key')
    expect(mocks.preloadTurnstileScript).toHaveBeenCalledTimes(1)
  })

  it('keeps retry fail-closed when the configuration request still fails', async () => {
    mocks.api.mockRejectedValue(new Error('network unavailable'))

    const { useTurnstileConfig } = await import('./useTurnstileConfig')
    const turnstile = useTurnstileConfig()

    await turnstile.loadTurnstileConfig()
    await turnstile.retryTurnstileConfig()

    expect(mocks.resetTurnstileScriptLoad).toHaveBeenCalledTimes(1)
    expect(turnstile.isTurnstileBlocked.value).toBe(true)
    expect(turnstile.turnstileSiteKey.value).toBe('')
  })
})
