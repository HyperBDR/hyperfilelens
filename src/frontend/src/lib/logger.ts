import { getEffectiveOrgKey, currentUser } from '../composables/useAuth'

const TRACE_STORAGE_KEY = 'hfl_trace_id'
const SERVICE = 'frontend'

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR'

function generateTraceId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(4))
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `t-${hex}`
}

/** Current trace id for this browser tab (created on first use). */
export function getTraceId(): string {
  try {
    let id = sessionStorage.getItem(TRACE_STORAGE_KEY)
    if (!id) {
      id = generateTraceId()
      sessionStorage.setItem(TRACE_STORAGE_KEY, id)
    }
    return id
  } catch {
    return generateTraceId()
  }
}

/** Sync trace id from backend ``X-Request-Id`` response header. */
export function setTraceId(id: string): void {
  const trimmed = id.trim()
  if (!trimmed) return
  try {
    sessionStorage.setItem(TRACE_STORAGE_KEY, trimmed.startsWith('t-') ? trimmed : `t-${trimmed}`)
  } catch {
    // ignore storage failures
  }
}

function formatOrgUser(): string {
  const org = getEffectiveOrgKey()
  const userId = currentUser.value?.id
  const orgPart = org ? `org-${org}` : '-'
  const userPart = userId ? `u-${userId}` : '-'
  return `${orgPart}/${userPart}`
}

function formatTimestamp(): string {
  const now = new Date()
  const base = now.toISOString().replace(/\.\d{3}Z$/, '')
  return `${base}.${now.getMilliseconds().toString().padStart(3, '0')}Z`
}

function hostLabel(): string {
  if (typeof window === 'undefined') return 'browser'
  return window.location.hostname || 'browser'
}

function renderLine(level: LogLevel, module: string, line: number, message: string, extra?: unknown): string {
  const trace = getTraceId()
  const orgUser = formatOrgUser()
  let body = message
  if (extra !== undefined) {
    if (typeof extra === 'object' && extra !== null) {
      try {
        body += `: ${JSON.stringify(extra)}`
      } catch {
        body += `: ${String(extra)}`
      }
    } else {
      body += `: ${String(extra)}`
    }
  }
  return `[${formatTimestamp()}] [${level}] [${hostLabel()}:0] [${trace}] [${orgUser}] [${SERVICE}(${module}:${line})] - ${body}`
}

function emit(level: LogLevel, module: string, line: number, message: string, extra?: unknown): void {
  const lineText = renderLine(level, module, line, message, extra)
  switch (level) {
    case 'ERROR':
      console.error(lineText)
      break
    case 'WARN':
      console.warn(lineText)
      break
    case 'DEBUG':
      console.debug(lineText)
      break
    default:
      console.info(lineText)
  }
}

/** Unified frontend logger matching backend/agent log line format. */
export const logger = {
  debug(module: string, line: number, message: string, extra?: unknown) {
    emit('DEBUG', module, line, message, extra)
  },
  info(module: string, line: number, message: string, extra?: unknown) {
    emit('INFO', module, line, message, extra)
  },
  warn(module: string, line: number, message: string, extra?: unknown) {
    emit('WARN', module, line, message, extra)
  },
  error(module: string, line: number, message: string, extra?: unknown) {
    emit('ERROR', module, line, message, extra)
  },
}
