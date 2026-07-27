import { describe, expect, it } from 'vitest'
import { resolveSafeLoginRedirect, withoutLegacySessionReason } from './loginNavigation'

const ORIGIN = 'https://hyperfilelens.com'

describe('login redirect validation', () => {
  it.each([
    ['/ops/alerts/incidents', '/ops/alerts/incidents'],
    ['/search?q=backup#results', '/search?q=backup#results'],
    ['/foo/../ops/task', '/ops/task'],
  ])('accepts and canonicalizes a local path: %s', (redirect, expected) => {
    expect(resolveSafeLoginRedirect(redirect, ORIGIN)).toBe(expected)
  })

  it.each([
    'https://example.com/steal',
    '//example.com/steal',
    '/\\example.com/steal',
    '/login',
    '/login/',
    '/LOGIN',
    '/Login/',
    '/login?redirect=/ops/task',
    '/foo/../login',
    '/foo/../LOGIN',
    '/%2e%2e/login',
    '/%252e%252e/login',
    '/%2f%2fexample.com',
    '/%255cexample.com',
    '/path\nnext',
  ])('rejects an unsafe or looping target: %s', (redirect) => {
    expect(resolveSafeLoginRedirect(redirect, ORIGIN)).toBeNull()
  })

  it('rejects non-string query values', () => {
    expect(resolveSafeLoginRedirect(['/ops/task'], ORIGIN)).toBeNull()
    expect(resolveSafeLoginRedirect(undefined, ORIGIN)).toBeNull()
  })
})

describe('legacy session reason cleanup', () => {
  it('removes reason while preserving valid navigation context', () => {
    expect(withoutLegacySessionReason({
      reason: 'TOKEN_REUSED',
      redirect: '/ops/alerts/incidents',
      email: 'person@example.com',
    })).toEqual({
      redirect: '/ops/alerts/incidents',
      email: 'person@example.com',
    })
  })

  it('does not redirect a clean login route', () => {
    expect(withoutLegacySessionReason({ redirect: '/ops/task' })).toBeNull()
  })
})
