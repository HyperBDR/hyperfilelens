// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import { issuePlatformGatewayEnrollmentInstall } from './nodeApi'

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()
  return {
    ...actual,
    api: vi.fn(),
  }
})

vi.mock('../composables/useAuth', () => ({
  getEffectiveOrgKey: vi.fn(() => ''),
}))

afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('platform Data Gateway enrollment', () => {
  it('uses the tenant API base returned by the Admin Console API', async () => {
    vi.stubGlobal('window', {
      location: { origin: 'https://console.example.com:11444' },
    })
    vi.mocked(api).mockResolvedValue({
      token: 'platform-token',
      token_id: 17,
      org_key: '__platform_lens__',
      gateway_scope: 'platform',
      api_base: 'https://console.example.com:11443',
    })

    const result = await issuePlatformGatewayEnrollmentInstall()

    expect(result.command).toContain(
      "curl -k 'https://console.example.com:11443/api/v1/node/enrollment/bootstrap-gateway?",
    )
    expect(result.command).toContain('api_base=https%3A%2F%2Fconsole.example.com%3A11443')
    expect(result.command).not.toContain('11444')
  })

  it('rejects an incomplete response instead of falling back to the Admin origin', async () => {
    vi.stubGlobal('window', {
      location: { origin: 'https://console.example.com:11444' },
    })
    vi.mocked(api).mockResolvedValue({
      token: 'platform-token',
      token_id: 17,
      org_key: '__platform_lens__',
    })

    await expect(issuePlatformGatewayEnrollmentInstall()).rejects.toThrow(
      'Platform gateway enrollment response is incomplete',
    )
  })
})
