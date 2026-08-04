// @vitest-environment jsdom

import { Buffer } from 'node:buffer'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import {
  buildEnrollmentInstallCommand,
  auditPlatformGatewayEnrollmentCopy,
  fetchLifecycleWatch,
  issueGatewayEnrollmentInstall,
  issuePlatformGatewayEnrollmentInstall,
  previewNodeOperationsBatch,
  revokePlatformGatewayEnrollment,
  startNodeOperation,
  startNodeOperationsBatch,
  fetchMinimalInstallerManifest,
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

const installerManifest = {
  schema_version: 1,
  artifacts: {
    'linux-amd64': { filename: '0.1.0/hfl-installer-linux-amd64.tar.gz', sha256: 'a'.repeat(64), size: 100 },
    'linux-arm64': { filename: '0.1.0/hfl-installer-linux-arm64.tar.gz', sha256: 'b'.repeat(64), size: 100 },
    'darwin-amd64': { filename: '0.1.0/hfl-installer-darwin-amd64.tar.gz', sha256: 'c'.repeat(64), size: 100 },
    'darwin-arm64': { filename: '0.1.0/hfl-installer-darwin-arm64.tar.gz', sha256: 'd'.repeat(64), size: 100 },
    'windows-amd64': { filename: '0.1.0/hfl-installer-windows-amd64.zip', sha256: 'e'.repeat(64), size: 100 },
  },
}

function stubInstallerManifest() {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => installerManifest,
  }))
}

function decodePowerShellCommand(command: string): string {
  const encoded = command.split(' ').at(-1) ?? ''
  return Buffer.from(encoded, 'base64').toString('utf16le')
}

describe('Minimal installer metadata', () => {
  it('accepts the standard API envelope used by local and production consoles', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        code: 0,
        message: 'success',
        data: installerManifest,
      }),
    }))

    await expect(fetchMinimalInstallerManifest()).resolves.toEqual(installerManifest)
  })

  it('rejects malformed artifact metadata before issuing a command', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...installerManifest,
        artifacts: {
          ...installerManifest.artifacts,
          'linux-amd64': {
            filename: '../unexpected.tar.gz',
            sha256: 'invalid',
            size: 0,
          },
        },
      }),
    }))

    await expect(fetchMinimalInstallerManifest()).rejects.toThrow(
      'Minimal installer metadata is invalid',
    )
  })
})

describe('Data Gateway enrollment', () => {
  it('uses strict TLS for a tenant Gateway when required by the backend', async () => {
    stubInstallerManifest()
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
    expect(result.command).toContain("base='https://hyperfilelens.com'")
    expect(result.command).toContain('"$base/media/enroll-bootstrap/$file"')
    expect(result.command).not.toContain('curl -k')
    expect(result.tlsVerify).toBe(true)
  })

  it('uses the tenant API base returned by the Admin Console API', async () => {
    stubInstallerManifest()
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
      expires_at: '2026-07-28T06:00:00Z',
    })

    const result = await issuePlatformGatewayEnrollmentInstall()

    expect(result.command).toContain("curl --proto '=https' --tlsv1.2")
    expect(result.command).toContain("base='https://console.example.com:11443'")
    expect(result.command).toContain('"$base/media/enroll-bootstrap/$file"')
    expect(result.command).toContain("HFL_API_BASE='https://console.example.com:11443'")
    expect(result.command).not.toContain('curl -k')
    expect(result.tlsVerify).toBe(true)
    expect(result.expiresAt).toBe('2026-07-28T06:00:00Z')
    expect(result.command).not.toContain('11444')
    expect(vi.mocked(api)).toHaveBeenCalledWith(
      '/api/v1/platform-ops/lens/gateways/enrollment',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ note: 'deploy:platform-gateway' }),
      }),
    )
  })

  it('keeps the explicit insecure mode for self-hosted deployments', async () => {
    stubInstallerManifest()
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
    expect(result.command).toContain('--location --progress-bar')
    expect(result.tlsVerify).toBe(false)
  })

  it('rejects an incomplete response instead of falling back to the Admin origin', async () => {
    stubInstallerManifest()
    vi.stubGlobal('window', {
      location: { origin: 'https://console.example.com:11444' },
    })
    vi.mocked(api).mockResolvedValue({
      token: 'platform-token',
      token_id: 17,
      org_key: '__platform_lens__',
    })

    await expect(issuePlatformGatewayEnrollmentInstall()).rejects.toThrow(
      'Public Data Gateway enrollment response is incomplete',
    )
  })

  it('uses dedicated platform endpoints to revoke and audit command copies', async () => {
    vi.mocked(api).mockResolvedValue({})

    await auditPlatformGatewayEnrollmentCopy(17)
    await revokePlatformGatewayEnrollment(17)

    expect(vi.mocked(api).mock.calls).toEqual([
      ['/api/v1/platform-ops/lens/gateways/enrollment/17/copied', { method: 'POST' }],
      ['/api/v1/platform-ops/lens/gateways/enrollment/17', { method: 'DELETE' }],
    ])
  })

  it('does not disable certificate validation in strict Windows commands', () => {
    const command = buildEnrollmentInstallCommand({
      org: 'tenant-a',
      role: 'agent',
      token: 'token-a',
      apiBase: 'https://console.example.com',
      os: 'windows',
      tlsVerify: true,
      manifest: installerManifest,
    })

    const script = decodePowerShellCommand(command)
    expect(script).not.toContain('ServerCertificateValidationCallback')
    expect(script).not.toContain('Write-Warning')
  })

  it('runs directly as root and only falls back to sudo for non-root users', () => {
    const command = buildEnrollmentInstallCommand({
      org: 'tenant-a',
      role: 'agent',
      token: 'token-a',
      apiBase: 'https://console.example.com',
      os: 'linux',
      tlsVerify: true,
      manifest: installerManifest,
    })

    expect(command).toContain('if [ "$(id -u)" -eq 0 ]')
    expect(command).toContain('elif command -v sudo >/dev/null 2>&1')
    expect(command).toContain("echo 'Administrator privileges are required. Re-run as root or install sudo.'")
  })

  it('does not issue a token when installer metadata is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))

    await expect(issueGatewayEnrollmentInstall({ orgKey: 'tenant-a' })).rejects.toThrow(
      'Minimal installer metadata is unavailable',
    )

    expect(vi.mocked(api)).not.toHaveBeenCalled()
  })

  it('retains the explicit Windows bypass for self-hosted deployments', () => {
    const command = buildEnrollmentInstallCommand({
      org: 'tenant-a',
      role: 'agent',
      token: 'token-a',
      apiBase: 'https://console.example.com',
      os: 'windows',
      tlsVerify: false,
      manifest: installerManifest,
    })

    const script = decodePowerShellCommand(command)
    expect(script).toContain('ServerCertificateValidationCallback')
    expect(script).toContain('Write-Warning')
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
