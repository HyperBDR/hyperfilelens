import {
  ERROR_CODE_FALLBACK_EN,
  ERROR_CODE_I18N_KEYS,
  isBrowserNetworkMessage,
  isRegistryCode,
} from './registry'
import { normalizeThrownError } from './normalizer'
import type { AppErrorShape } from './types'

export type TranslateFn = (key: string, params?: Record<string, unknown>) => string

function interpolate(template: string, params?: Record<string, unknown>): string {
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = params[key]
    return value == null ? '' : String(value)
  })
}

function metaFromError(err: AppErrorShape): Record<string, unknown> | undefined {
  if (err.meta && typeof err.meta === 'object') return err.meta
  return undefined
}

function firstFieldError(fields: Record<string, string[]> | undefined): string | undefined {
  if (!fields) return undefined
  for (const messages of Object.values(fields)) {
    const message = messages.find((item) => item.trim())
    if (message) return message
  }
  return undefined
}

export function resolveErrorCode(err: unknown): string {
  const normalized = normalizeThrownError(err)
  const code = normalized.errorCode || normalized.code || ''
  if (isRegistryCode(code)) return code
  if (normalized.message && isBrowserNetworkMessage(normalized.message)) return 'NETWORK.UNAVAILABLE'
  return code || 'UNKNOWN.ERROR'
}

export function resolveErrorMessage(
  err: unknown,
  t?: TranslateFn,
  fallback = 'Request failed',
): string {
  const normalized = normalizeThrownError(err)
  const code = resolveErrorCode(err)
  const meta = metaFromError(normalized)

  if (code === 'CLIENT.ABORTED') return ''

  if (code === 'VALIDATION.FAILED') {
    const fieldMessage = firstFieldError(normalized.fields)
    if (fieldMessage) return fieldMessage
  }

  if (t && isRegistryCode(code)) {
    const key = ERROR_CODE_I18N_KEYS[code]
    if (key) return interpolate(t(key, meta), meta)
  }

  if (isRegistryCode(code)) {
    return interpolate(ERROR_CODE_FALLBACK_EN[code] || fallback, meta)
  }

  if (normalized.message && !isBrowserNetworkMessage(normalized.message)) {
    const legacyAgentMessage = humanizeLegacyAgentWsMessage(normalized.message, t)
    if (legacyAgentMessage) return legacyAgentMessage
  }

  if (normalized.message && isBrowserNetworkMessage(normalized.message)) {
    return t
      ? interpolate(t(ERROR_CODE_I18N_KEYS['NETWORK.UNAVAILABLE']), meta)
      : ERROR_CODE_FALLBACK_EN['NETWORK.UNAVAILABLE']
  }

  return fallback
}

export function resolveErrorMessageI18n(
  err: unknown,
  t: TranslateFn,
  fallback = 'Request failed',
): string {
  return resolveErrorMessage(err, t, fallback)
}

const LEGACY_AGENT_WS_NOT_ROUTABLE = 'agent websocket is not routable'
const LEGACY_AGENT_WS_RECONNECTING = 'agent websocket is reconnecting'

function humanizeLegacyAgentWsMessage(message: string, t?: TranslateFn): string | null {
  const normalized = message.trim().toLowerCase()
  if (normalized.includes(LEGACY_AGENT_WS_NOT_ROUTABLE)) {
    if (t) return t('errors.agentWsNotRoutable')
    return 'The agent node is offline or unreachable. Wait until the host is back online and try again, or enable force delete to skip remote cleanup.'
  }
  if (normalized.includes(LEGACY_AGENT_WS_RECONNECTING)) {
    if (t) return t('errors.agentWsReconnecting')
    return 'The agent node is reconnecting. Wait a moment and try again.'
  }
  return null
}

/** Map internal agent websocket errors in plain strings to user-facing copy. */
export function humanizeLegacyErrorMessage(
  message: string,
  t?: TranslateFn,
  fallback?: string,
): string {
  const trimmed = message.trim()
  if (!trimmed) return fallback ?? ''
  const legacy = humanizeLegacyAgentWsMessage(trimmed, t)
  if (legacy) return legacy
  return trimmed
}
