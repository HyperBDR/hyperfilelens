import type { LocationQuery, LocationQueryRaw } from 'vue-router'

export const LOGIN_ROUTE_NAME = 'login'

const ENCODED_PATH_DELIMITER_PATTERN = /%(?:25)*(?:2e|2f|5c)/i

function containsControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const code = character.charCodeAt(0)
    return code <= 31 || code === 127
  })
}

function currentOrigin(): string {
  return typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
}

export function resolveSafeLoginRedirect(
  redirect: unknown,
  origin = currentOrigin(),
): string | null {
  if (typeof redirect !== 'string') return null
  if (!redirect.startsWith('/') || redirect.startsWith('//')) return null
  if (redirect.includes('\\') || containsControlCharacter(redirect)) return null

  try {
    const expectedOrigin = new URL(origin).origin
    const target = new URL(redirect, expectedOrigin)
    if (target.origin !== expectedOrigin) return null
    if (ENCODED_PATH_DELIMITER_PATTERN.test(target.pathname)) return null
    const normalizedPath = target.pathname.toLowerCase()
    if (normalizedPath === '/login' || normalizedPath.startsWith('/login/')) return null
    return `${target.pathname}${target.search}${target.hash}`
  } catch {
    return null
  }
}

export function withoutLegacySessionReason(query: LocationQuery): LocationQueryRaw | null {
  if (!Object.prototype.hasOwnProperty.call(query, 'reason')) return null
  const sanitized: LocationQueryRaw = { ...query }
  delete sanitized.reason
  return sanitized
}
