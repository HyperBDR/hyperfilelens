import { afterEach, describe, expect, it } from 'vitest'
import {
  closeErrorDetails,
  errorDetailsCopyText,
  errorDetailsState,
  openErrorDetails,
  safeErrorDetailText,
  toErrorDetails,
} from './details'

describe('error details', () => {
  afterEach(closeErrorDetails)

  it('maps structured application errors', () => {
    const details = toErrorDetails({
      status: 504,
      message: 'Connection timed out',
      errorCode: 'STORAGE.TIMEOUT',
      traceId: 'trace-001',
      detail: { endpoint: 'https://example.invalid' },
    })

    expect(details.errorCode).toBe('STORAGE.TIMEOUT')
    expect(details.traceId).toBe('trace-001')
    expect(details.issue).toBe('Connection timed out')
  })

  it('redacts secrets from objects and raw strings', () => {
    const text = safeErrorDetailText({
      endpoint: 'https://example.invalid',
      secret_access_key: 'super-secret',
      nested: { authorization: 'Bearer abc.def.ghi' },
      raw: 'password=hunter2 token: abc123',
    })

    expect(text).toContain('https://example.invalid')
    expect(text).not.toContain('super-secret')
    expect(text).not.toContain('abc.def.ghi')
    expect(text).not.toContain('hunter2')
    expect(text).not.toContain('abc123')
    expect(text).toContain('[REDACTED]')
  })

  it('redacts secrets embedded in the visible issue and copied text', () => {
    const details = toErrorDetails(new Error('password=hunter2 request failed'))
    expect(details.issue).not.toContain('hunter2')
    expect(errorDetailsCopyText(details)).not.toContain('hunter2')
  })

  it('builds copyable diagnostic text and controls the global dialog state', () => {
    const payload = {
      title: 'Connection failed',
      summary: 'Unable to connect',
      errorCode: 'NETWORK.TIMEOUT',
      traceId: 'trace-002',
      issue: 'The endpoint timed out.',
      reasons: ['The endpoint is offline.'],
      resolutions: ['Check the endpoint.'],
    }
    openErrorDetails(payload)
    expect(errorDetailsState.current?.errorCode).toBe('NETWORK.TIMEOUT')
    expect(errorDetailsCopyText(payload)).toContain('How to resolve')
    closeErrorDetails()
    expect(errorDetailsState.current).toBeNull()
  })
})
