import type { PlatformAuditLog } from '../lib/platformOpsApi'

const ACTION_LABELS: Record<string, string> = {
  'support.enter': 'Enter Customer Support Mode',
  'support.exit': 'Exit Customer Support Mode',
  'user.create': 'Create User',
  'user.update': 'Update User',
  'user.delete': 'Delete User',
  'user.reset_password': 'Reset User Password',
  'org.create': 'Create Customer Account',
  'org.update': 'Update Customer Account',
  'org.delete': 'Delete Customer Account',
  'plan.create': 'Create Billing Plan',
  'plan.update': 'Update Billing Plan',
  'subscription.update': 'Update Subscription',
  'quota.update': 'Update Quota',
  'gateway.enrollment.generate': 'Generate Gateway Enrollment Command',
  'gateway.enrollment.copy': 'Copy Gateway Enrollment Command',
  'gateway.enrollment.revoke': 'Revoke Gateway Enrollment Command',
  'node.lifecycle.upgrade': 'Upgrade Node',
  'node.lifecycle.remove': 'Remove Node',
  'monitoring.incident.acknowledge': 'Acknowledge Incident',
  'monitoring.incident.resolve': 'Resolve Incident',
  'monitoring.task.cancel': 'Cancel Task',
  'monitoring.task.retry': 'Retry Task',
  'monitoring.notification.retry': 'Retry Notification Delivery',
  'storage_provider.import.diff': 'Compare Provider Catalog Import',
  'storage_provider.import.review': 'Review Provider Catalog Import',
  'storage_provider.import.apply': 'Apply Provider Catalog Import',
  'storage_provider.catalog.export': 'Export Provider Catalog',
  'storage_provider.reset.review': 'Review Provider Reset',
  'storage_provider.reset': 'Reset Storage Provider',
  'storage_provider.validation.create': 'Start Provider Validation',
  'storage_provider.validation.cancel': 'Cancel Provider Validation',
  'storage_provider.validation.retry': 'Retry Provider Validation',
}

const TARGET_LABELS: Record<string, string> = {
  user: 'User',
  organization: 'Customer Account',
  org: 'Customer Account',
  node: 'Node',
  node_token: 'Gateway Enrollment Token',
  incident: 'Incident',
  task: 'Task',
  notification: 'Notification Delivery',
  storage_provider: 'Storage Provider',
  platform_settings: 'Platform Settings',
  subscription: 'Subscription',
  plan: 'Billing Plan',
  quota: 'Quota',
}

function humanize(value: string) {
  return value
    .replace(/[._-]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .trim()
}

export function platformAuditActionLabel(action?: string | null) {
  const value = String(action || '').trim()
  return ACTION_LABELS[value] || humanize(value) || 'Unknown Action'
}

export function platformAuditTargetTypeLabel(targetType?: string | null) {
  const value = String(targetType || '').trim()
  return TARGET_LABELS[value] || humanize(value) || 'Platform'
}

export function platformAuditTargetSecondary(row: PlatformAuditLog) {
  const id = String(row.target_id || '').trim()
  if (!id) return row.org_key ? `Account: ${row.org_key}` : 'Platform scope'
  return `ID: ${id}`
}

export function platformAuditResultLabel(result?: string | null) {
  const value = String(result || '').trim().toLowerCase()
  if (value === 'success') return 'Succeeded'
  if (value === 'failure' || value === 'failed') return 'Failed'
  if (value === 'partial') return 'Partially Succeeded'
  return humanize(value) || 'Unknown'
}

export function platformAuditHasDetails(details?: Record<string, unknown> | null) {
  return Boolean(details && Object.keys(details).length > 0)
}
