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
    expect(locale).toContain("installFlowDownload: 'Downloads the Agent to this host'")
    expect(locale).toContain("installFlowInstall: 'Installs and configures the Agent'")
  })

  it('uses accurate role-specific platform and storage guidance', () => {
    const wizard = source('src/components/NodeLifecycleWizard.vue')
    const locale = source('src/locales/en.ts')

    expect(wizard).toContain("props.role === 'gateway'")
    expect(wizard).toContain("t('nodesDeploy.gatewayReqDiskSub')")
    expect(locale).toContain("proxyReqDisk: '50GB+ storage'")
    expect(locale).not.toContain('100GB+')
    expect(locale).toContain('Ubuntu 20.04, 22.04, or 24.04 LTS · amd64')
    expect(locale).toContain("gatewayReqDiskSub: 'Local runtime and workspace storage'")
    expect(locale).toContain('Registers the Data Gateway with the console')
  })
})
