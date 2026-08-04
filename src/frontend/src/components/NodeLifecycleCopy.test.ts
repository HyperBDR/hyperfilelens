import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), 'utf8')
}

describe('Node lifecycle copy', () => {
  it('keeps headings and action copy consistent', () => {
    const locale = source('src/locales/en.ts')

    expect(locale).toContain("installCommandStep: 'Run the Install Command'")
    expect(locale).toContain("generateInstallCommand: 'Generate install command'")
    expect(locale).toContain('Copy the command and run it in a shell on the target host')
    expect(locale).toContain("installFlowDownload: 'Downloads the small installer and checks the target host'")
    expect(locale).toContain("installFlowInstall: 'Downloads the required components and installs the Agent'")
  })

  it('uses accurate role-specific platform and storage guidance', () => {
    const wizard = source('src/components/NodeLifecycleWizard.vue')
    const locale = source('src/locales/en.ts')

    expect(wizard).toContain("props.role === 'gateway'")
    expect(wizard).toContain("t('nodesDeploy.gatewayReqDiskSub')")
    expect(locale).toContain("proxyReqDisk: '50GB+ storage'")
    expect(locale).not.toContain('100GB+')
    expect(locale).toContain('Ubuntu 20.04, 22.04, or 24.04 LTS')
    expect(locale).toContain('amd64')
    expect(locale).toContain("gatewayReqDiskSub: 'Local runtime and workspace storage'")
    expect(locale).toContain('Registers a Public Data Gateway with HyperFileLens')
    expect(locale).toContain('Registers a Private Data Gateway with HyperFileLens')
  })

  it('revokes enrollment tokens discarded by command regeneration', () => {
    const wizard = source('src/components/NodeLifecycleWizard.vue')

    expect(wizard).toContain('await revokeIssuedEnrollment(issued.tokenId, platformEnrollment)')
    expect(wizard).toContain('void revokeIssuedEnrollment(staleTokenId, staleTokenIsPlatform)')
    expect(wizard).toContain('enrollmentTokenIsPlatform.value')
    expect(wizard).toContain('await revokeEnrollmentToken(tokenId).catch(() => undefined)')
    expect(wizard).toContain('await revokeEnrollmentToken(issuedTokenId).catch(() => undefined)')
    expect(wizard).toContain('release.expires_in ?? 600')
    expect(wizard).not.toContain('installError.value')
  })

  it('shows expiry without host quotas or replacement-command controls', () => {
    const wizard = source('src/components/NodeLifecycleWizard.vue')
    const locale = source('src/locales/en.ts')

    expect(wizard).toContain('tokenValidityLabel')
    expect(locale).toContain("installCommandValidFor: 'Valid for {hours}h {minutes}m'")
    expect(wizard).not.toContain('tokenCapacityLabel')
    expect(wizard).not.toContain('replaceInstallCommand')
    expect(locale).not.toContain('installs left')
    expect(locale).not.toContain("generateNewInstallCommand: 'New command'")
  })
})
