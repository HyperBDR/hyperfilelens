import { describe, expect, it } from 'vitest'

import { buildLocalUpgradeCommand } from './nodeInstallCommands'

describe('node upgrade download TLS policy', () => {
  it('uses strict TLS for SaaS Gateway upgrades', () => {
    const command = buildLocalUpgradeCommand(
      'linux',
      '/tmp/hfl-agent.tar.gz',
      true,
      'https://hyperfilelens.com/agent.tar.gz',
      'gateway',
      true,
    )

    expect(command).toContain("curl --proto '=https' --tlsv1.2 -fL")
    expect(command).not.toContain('curl -k')
  })

  it('retains the explicit self-hosted TLS bypass', () => {
    const command = buildLocalUpgradeCommand(
      'linux',
      '/tmp/hfl-agent.tar.gz',
      true,
      'https://hfl.localhost/agent.tar.gz',
      'gateway',
      false,
    )

    expect(command).toContain('curl -k -fL')
  })

  it('does not add -k to strict Windows downloads', () => {
    const command = buildLocalUpgradeCommand(
      'windows',
      'C:\\Temp\\hfl-agent.zip',
      true,
      'https://hyperfilelens.com/agent.zip',
      'agent',
      true,
    )

    expect(command).toContain('curl.exe -fL')
    expect(command).not.toContain('curl.exe -k')
  })
})
