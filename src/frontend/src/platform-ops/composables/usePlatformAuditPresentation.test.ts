import { describe, expect, it } from 'vitest'
import {
  platformAuditActionLabel,
  platformAuditHasDetails,
  platformAuditResultLabel,
  platformAuditTargetSecondary,
  platformAuditTargetTypeLabel,
} from './usePlatformAuditPresentation'

describe('platform audit presentation', () => {
  it('presents known operator actions and safely humanizes future actions', () => {
    expect(platformAuditActionLabel('support.enter')).toBe('Enter Customer Support Mode')
    expect(platformAuditActionLabel('gateway.enrollment.revoke')).toBe('Revoke Gateway Enrollment Command')
    expect(platformAuditActionLabel('future_action.run-now')).toBe('Future Action Run Now')
  })

  it('separates target type and identifier', () => {
    const row = { target_id: '42', org_key: 'customer-a' } as Parameters<typeof platformAuditTargetSecondary>[0]
    expect(platformAuditTargetTypeLabel('node_token')).toBe('Gateway Enrollment Token')
    expect(platformAuditTargetSecondary(row)).toBe('ID: 42')
  })

  it('uses user-facing result labels and meaningful empty details', () => {
    expect(platformAuditResultLabel('success')).toBe('Succeeded')
    expect(platformAuditResultLabel('failure')).toBe('Failed')
    expect(platformAuditHasDetails({})).toBe(false)
    expect(platformAuditHasDetails({ reason: 'manual' })).toBe(true)
  })
})
