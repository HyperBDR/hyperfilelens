import type { EnrollmentOs } from './nodeApi'
import type { NodeRole } from '../types/node'

const LINUX_INSTALL_DIR = '/opt/hyperfilelens-agent'
const LINUX_DATA_DIR = '/var/lib/hyperfilelens-agent'
const MAC_LAUNCHD_LABEL = 'com.hyperfilelens.agent'
const WIN_INSTALL_CMD = '& "$env:ProgramFiles\\HyperFileLens\\Agent\\install.cmd"'

export type NodeLifecycleTab = 'install' | 'upgrade' | 'uninstall' | 'service'

function curlDownloadOptions(tlsVerify: boolean): string {
  return tlsVerify ? "--proto '=https' --tlsv1.2 -fL" : '-k -fL'
}

/** Proxy and gateway nodes are supported on Linux only (NAS mount deps). */
export const LINUX_ONLY_ROLES: NodeRole[] = ['proxy', 'gateway']

export function isLinuxOnlyRole(role: NodeRole): boolean {
  return LINUX_ONLY_ROLES.includes(role)
}

export function roleSupportedOnOs(role: NodeRole, os: EnrollmentOs): boolean {
  if (isLinuxOnlyRole(role)) return os === 'linux'
  return true
}

export function linuxInstallScriptPath() {
  return `${LINUX_INSTALL_DIR}/install.sh`
}

export function buildLocalUpgradeCommand(
  os: EnrollmentOs,
  packagePath: string,
  withDownload = false,
  downloadUrl = '',
  role?: NodeRole,
  tlsVerify = true,
) {
  const pkg = packagePath.trim() || '/path/to/hfl-agent-*.tar.gz'
  if (role === 'gateway' && os === 'linux') {
    const archive = pkg.endsWith('.tar.gz') ? pkg : '/tmp/hfl-agent.tar.gz'
    if (withDownload && downloadUrl) {
      return `curl ${curlDownloadOptions(tlsVerify)} -o ${archive} '${downloadUrl}'\nsudo hfl-enroll gateway-upgrade --from ${archive}`
    }
    return `sudo hfl-enroll gateway-upgrade --from ${archive}`
  }
  if (os === 'windows') {
    const zip = pkg.endsWith('.zip') ? pkg : 'C:\\path\\to\\hfl-agent-*.zip'
    if (withDownload && downloadUrl) {
      const insecure = tlsVerify ? '' : ' -k'
      return `curl.exe${insecure} -fL -o "${zip}" "${downloadUrl}"\r\n${WIN_INSTALL_CMD} upgrade -From "${zip}"`
    }
    return `${WIN_INSTALL_CMD} upgrade -From "${zip}"`
  }
  const archive = pkg.endsWith('.tar.gz') ? pkg : '/tmp/hfl-agent.tar.gz'
  if (withDownload && downloadUrl) {
    return `curl ${curlDownloadOptions(tlsVerify)} -o ${archive} '${downloadUrl}'\nsudo ${linuxInstallScriptPath()} upgrade --from ${archive}`
  }
  return `sudo ${linuxInstallScriptPath()} upgrade --from ${archive}`
}

export function buildLocalUninstallCommand(os: EnrollmentOs, purgeAll = true, role?: NodeRole) {
  if (role === 'gateway' && os === 'linux') {
    return purgeAll
      ? 'sudo hfl-enroll gateway-uninstall'
      : 'sudo hfl-enroll gateway-uninstall --keep-data'
  }
  if (os === 'windows') {
    return purgeAll
      ? `${WIN_INSTALL_CMD} uninstall -PurgeAll`
      : `${WIN_INSTALL_CMD} uninstall`
  }
  return purgeAll
    ? `sudo ${linuxInstallScriptPath()} uninstall --purge-all`
    : `sudo ${linuxInstallScriptPath()} uninstall`
}

export function buildLocalServiceCommand(os: EnrollmentOs, action: 'status' | 'start' | 'stop' | 'restart') {
  if (os === 'windows') {
    if (action === 'status') return `${WIN_INSTALL_CMD} status`
    if (action === 'start') return 'Start-Service HyperFileLensAgent'
    if (action === 'stop') return 'Stop-Service HyperFileLensAgent -Force'
    return 'Restart-Service HyperFileLensAgent'
  }
  return `sudo ${linuxInstallScriptPath()} ${action}`
}

export function roleDeployNotes(role: NodeRole): string[] {
  switch (role) {
    case 'gateway':
      return ['noteGateway', 'noteGatewayLinuxOnly']
    case 'proxy':
      return ['noteProxy', 'noteProxyLinuxOnly']
    default:
      return []
  }
}

export function defaultPackagePath(os: EnrollmentOs, version?: string) {
  const ver = version?.trim() || '1.0.0'
  if (os === 'windows') {
    return `C:\\Users\\Administrator\\Downloads\\hfl-agent-${ver}-windows-amd64.zip`
  }
  if (os === 'macos') {
    return `/tmp/hfl-agent-${ver}-darwin-arm64.tar.gz`
  }
  return `/tmp/hfl-agent-${ver}-linux-amd64.tar.gz`
}

export function installPathsSummary(os: EnrollmentOs) {
  if (os === 'windows') {
    return {
      installDir: 'C:\\Program Files\\HyperFileLens\\Agent',
      dataDir: 'C:\\ProgramData\\HyperFileLens\\Agent',
      service: 'HyperFileLensAgent',
    }
  }
  if (os === 'macos') {
    return {
      installDir: LINUX_INSTALL_DIR,
      dataDir: LINUX_DATA_DIR,
      service: `${MAC_LAUNCHD_LABEL} (LaunchDaemon)`,
    }
  }
  return {
    installDir: LINUX_INSTALL_DIR,
    dataDir: LINUX_DATA_DIR,
    service: 'hyperfilelens-agent.service',
  }
}
