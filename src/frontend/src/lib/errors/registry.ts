/** Registry code → i18n key under errors.codes.* */
export const ERROR_CODE_I18N_KEYS: Record<string, string> = {
  'NETWORK.UNAVAILABLE': 'errors.codes.networkUnavailable',
  'NETWORK.TIMEOUT': 'errors.codes.networkTimeout',
  'CLIENT.OFFLINE': 'errors.codes.clientOffline',
  'CLIENT.ABORTED': 'errors.codes.clientAborted',
  'UNKNOWN.ERROR': 'errors.codes.unknown',
  'VALIDATION.FAILED': 'errors.codes.validationFailed',
  'AUTH.FORBIDDEN': 'errors.codes.authForbidden',
  'RESOURCE.NOT_FOUND': 'errors.codes.resourceNotFound',
  'RESOURCE.CONFLICT': 'errors.codes.resourceConflict',
  'STORAGE.REPOSITORY_ALREADY_EXISTS': 'errors.codes.storageRepositoryAlreadyExists',
  'SERVER.INTERNAL_ERROR': 'errors.codes.serverInternal',
  'AGENT.TIMEOUT': 'errors.codes.agentTimeout',
  'AGENT.UNREACHABLE': 'errors.codes.agentUnreachable',
  'AGENT.EXPLORER_LIST_FAILED': 'errors.codes.agentExplorerListFailed',
  'AGENT.PATH_VALIDATE_FAILED': 'errors.codes.agentPathValidateFailed',
  'AGENT.NAS_MOUNT_FAILED': 'errors.codes.agentNasMountFailed',
  'AGENT.TASK_FAILED': 'errors.codes.agentTaskFailed',
  'BACKUP.QUOTA_EXCEEDED': 'errors.codes.backupQuotaExceeded',
  'BACKUP.ALREADY_RUNNING': 'errors.codes.backupAlreadyRunning',
  'RESTORE.ALREADY_RUNNING': 'errors.codes.restoreAlreadyRunning',
}

export const ERROR_CODE_FALLBACK_EN: Record<string, string> = {
  'NETWORK.UNAVAILABLE': 'Unable to connect. Check your network and try again.',
  'NETWORK.TIMEOUT': 'Request timed out. Please try again later.',
  'CLIENT.OFFLINE': 'You are offline. Check your network connection.',
  'UNKNOWN.ERROR': 'Something went wrong. Please try again.',
  'VALIDATION.FAILED': 'Please check the form and try again.',
  'AUTH.FORBIDDEN': "You don't have permission to perform this action.",
  'RESOURCE.NOT_FOUND': "This resource doesn't exist or was removed.",
  'STORAGE.REPOSITORY_ALREADY_EXISTS': 'A Kopia repository already exists at the selected location. Import is not supported in this version. Choose a different storage location.',
  'SERVER.INTERNAL_ERROR': 'Service is temporarily unavailable. Please try again later.',
  'AGENT.TIMEOUT': 'Agent timed out. Confirm the node is online and try again.',
  'AGENT.UNREACHABLE': 'Agent is unreachable. Confirm the node is online.',
  'AGENT.EXPLORER_LIST_FAILED': 'Failed to browse directory. Confirm the node is online and try again.',
  'AGENT.PATH_VALIDATE_FAILED': 'Path validation failed. Check the path and try again.',
  'AGENT.NAS_MOUNT_FAILED': 'NAS mount operation failed. Check connection settings.',
  'AGENT.TASK_FAILED': 'Agent task failed. Please try again.',
  'BACKUP.QUOTA_EXCEEDED': 'Backup quota exceeded. Upgrade your subscription and try again.',
  'BACKUP.ALREADY_RUNNING': 'A backup is already running for this source.',
  'RESTORE.ALREADY_RUNNING': 'A restore task is already running for this source.',
}

const BROWSER_NETWORK_PATTERNS = [
  'failed to fetch',
  'networkerror when attempting to fetch resource',
  'load failed',
  'network request failed',
]

export function isBrowserNetworkMessage(message: string): boolean {
  const m = message.trim().toLowerCase()
  return BROWSER_NETWORK_PATTERNS.some((p) => m.includes(p))
}

export function isRegistryCode(code: string): boolean {
  return Boolean(code && ERROR_CODE_I18N_KEYS[code])
}
