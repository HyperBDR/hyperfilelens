export const SESSION_NOTICE_REASONS = [
  'TOKEN_EXPIRED',
  'REFRESH_EXPIRED',
  'OTHER_DEVICE_LOGIN',
  'PASSWORD_CHANGED',
  'ACCOUNT_DISABLED',
  'TOKEN_REUSED',
  'INVALID_TOKEN',
  'TOKEN_BLACKLISTED',
] as const

export type SessionNoticeReason = (typeof SESSION_NOTICE_REASONS)[number]

const SESSION_INVALID_REASONS = new Set<SessionNoticeReason>([
  'OTHER_DEVICE_LOGIN',
  'PASSWORD_CHANGED',
  'ACCOUNT_DISABLED',
  'TOKEN_REUSED',
  'INVALID_TOKEN',
  'TOKEN_BLACKLISTED',
])

const SESSION_REASON_MESSAGE_KEYS: Record<SessionNoticeReason, string> = {
  TOKEN_EXPIRED: 'login.sessionExpired',
  REFRESH_EXPIRED: 'login.sessionExpired',
  OTHER_DEVICE_LOGIN: 'login.sessionOtherDevice',
  PASSWORD_CHANGED: 'login.sessionPasswordChanged',
  ACCOUNT_DISABLED: 'login.sessionAccountDisabled',
  TOKEN_REUSED: 'login.sessionTokenReused',
  INVALID_TOKEN: 'login.sessionInvalid',
  TOKEN_BLACKLISTED: 'login.sessionInvalid',
}

const SESSION_NOTICE_STORAGE_KEY = 'hyperfilelens:auth-session-notice'
const SESSION_NOTICE_VERSION = 1
export const SESSION_NOTICE_TTL_MS = 60_000

type StoredSessionNotice = {
  version: typeof SESSION_NOTICE_VERSION
  reason: SessionNoticeReason
  createdAt: number
}

function browserSessionStorage(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export function isSessionNoticeReason(reason: unknown): reason is SessionNoticeReason {
  return typeof reason === 'string' && SESSION_NOTICE_REASONS.includes(reason as SessionNoticeReason)
}

export function isSessionInvalidReason(reason: unknown): reason is SessionNoticeReason {
  return isSessionNoticeReason(reason) && SESSION_INVALID_REASONS.has(reason)
}

export function sessionNoticeMessageKey(reason: unknown): string | null {
  return isSessionNoticeReason(reason) ? SESSION_REASON_MESSAGE_KEYS[reason] : null
}

export function storeSessionNotice(
  reason: unknown,
  storage: Storage | null = browserSessionStorage(),
  now = Date.now(),
): boolean {
  if (!storage || !isSessionNoticeReason(reason)) return false

  const notice: StoredSessionNotice = {
    version: SESSION_NOTICE_VERSION,
    reason,
    createdAt: now,
  }

  try {
    storage.setItem(SESSION_NOTICE_STORAGE_KEY, JSON.stringify(notice))
    return true
  } catch {
    return false
  }
}

export function consumeSessionNotice(
  storage: Storage | null = browserSessionStorage(),
  now = Date.now(),
): SessionNoticeReason | null {
  if (!storage) return null

  let raw: string | null = null
  try {
    raw = storage.getItem(SESSION_NOTICE_STORAGE_KEY)
    storage.removeItem(SESSION_NOTICE_STORAGE_KEY)
  } catch {
    return null
  }
  if (!raw) return null

  try {
    const notice = JSON.parse(raw) as Partial<StoredSessionNotice>
    if (notice.version !== SESSION_NOTICE_VERSION) return null
    if (!isSessionNoticeReason(notice.reason)) return null
    if (typeof notice.createdAt !== 'number' || !Number.isFinite(notice.createdAt)) return null
    if (notice.createdAt > now || now - notice.createdAt > SESSION_NOTICE_TTL_MS) return null
    return notice.reason
  } catch {
    return null
  }
}
