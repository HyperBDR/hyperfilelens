// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import {
  buildEnrollmentInstallCommand,
  fetchLifecycleWatch,
  issueGatewayEnrollmentInstall,
  issuePlatformGatewayEnrollmentInstall,
  previewNodeOperationsBatch,
  startNodeOperation,
  startNodeOperationsBatch,
} from './nodeApi'

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
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('Data Gateway enrollment', () => {
  it('uses strict TLS for a tenant Gateway when required by the backend', async () => {
    vi.stubGlobal('window', {
      location: { origin: 'https://hyperfilelens.com' },
    })
    vi.mocked(api).mockResolvedValue({
      id: 18,
      token: 'tenant-token',
      role: 'gateway',
      is_active: true,
      tls_verify: true,
    })

    const result = await issueGatewayEnrollmentInstall({ orgKey: 'tenant-a' })

    expect(result.command).toContain("curl --proto '=https' --tlsv1.2")
    expect(result.command).toContain('https://hyperfilelens.com/api/v1/node/enrollment/')
    expect(result.command).not.toContain('curl -k')
    expect(result.tlsVerify).toBe(true)
  })

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
      tls_verify: true,
    })

    const result = await issuePlatformGatewayEnrollmentInstall()

    expect(result.command).toContain("curl --proto '=https' --tlsv1.2")
    expect(result.command).toContain(
      "'https://console.example.com:11443/api/v1/node/enrollment/bootstrap-gateway?",
    )
    expect(result.command).toContain('api_base=https%3A%2F%2Fconsole.example.com%3A11443')
    expect(result.command).not.toContain('curl -k')
    expect(result.tlsVerify).toBe(true)
    expect(result.command).not.toContain('11444')
  })

  it('keeps the explicit insecure mode for self-hosted deployments', async () => {
    vi.mocked(api).mockResolvedValue({
      token: 'platform-token',
      token_id: 17,
      org_key: '__platform_lens__',
      gateway_scope: 'platform',
      api_base: 'https://console.example.com:11443',
      tls_verify: false,
    })

    const result = await issuePlatformGatewayEnrollmentInstall()

    expect(result.command).toContain('TLS certificate verification is disabled')
    expect(result.command).toContain('curl -k --fail --show-error --location')
    expect(result.tlsVerify).toBe(false)
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

  it('does not disable certificate validation in strict Windows commands', () => {
    const command = buildEnrollmentInstallCommand({
      org: 'tenant-a',
      role: 'agent',
      token: 'token-a',
      apiBase: 'https://console.example.com',
      os: 'windows',
      tlsVerify: true,
    })

    expect(command).not.toContain('ServerCertificateValidationCallback')
    expect(command).not.toContain('Write-Warning')
  })

  it('retains the explicit Windows bypass for self-hosted deployments', () => {
    const command = buildEnrollmentInstallCommand({
      org: 'tenant-a',
      role: 'agent',
      token: 'token-a',
      apiBase: 'https://console.example.com',
      os: 'windows',
      tlsVerify: false,
    })

    expect(command).toContain('ServerCertificateValidationCallback')
    expect(command).toContain('Write-Warning')
  })
})

describe('platform Data Gateway lifecycle', () => {
  it('routes every lifecycle request through Platform Operations', async () => {
    vi.mocked(api).mockResolvedValue({ nodes: [] })

    await previewNodeOperationsBatch({
      kind: 'remove',
      nodeIds: [17],
      scope: 'platform',
    })
    await startNodeOperationsBatch({
      kind: 'remove',
      nodeIds: [17],
      scope: 'platform',
    })
    await startNodeOperation(17, 'remove', { scope: 'platform' })
    await fetchLifecycleWatch([17], 'platform')

    expect(vi.mocked(api).mock.calls.map(([path]) => path)).toEqual([
      '/api/v1/platform-ops/lens/gateways/operations/preview',
      '/api/v1/platform-ops/lens/gateways/operations/batch',
      '/api/v1/platform-ops/lens/gateways/17/operations',
      '/api/v1/platform-ops/lens/gateways/lifecycle-watch',
    ])
  })
})
