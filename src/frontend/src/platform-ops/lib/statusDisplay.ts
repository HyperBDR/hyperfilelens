/** Map domain status/severity strings to ops list status pill modifiers. */

const STATUS_ALIASES: Record<string, string> = {
  succeeded: 'success',
  completed: 'success',
  complete: 'success',
  success: 'success',
  resolved: 'success',
  online: 'success',
  active: 'success',
  ok: 'success',
  healthy: 'success',
  sent: 'success',
  delivered: 'success',
  failure: 'failed',
  failed: 'failed',
  error: 'failed',
  firing: 'failed',
  critical: 'failed',
  high: 'failed',
  offline: 'failed',
  inactive: 'failed',
  unhealthy: 'failed',
  running: 'running',
  in_progress: 'running',
  processing: 'running',
  acknowledged: 'running',
  ack: 'running',
  medium: 'running',
  warning: 'timeout',
  warn: 'timeout',
  timeout: 'timeout',
  timed_out: 'timeout',
  pending: 'pending',
  queued: 'pending',
  waiting: 'pending',
  low: 'pending',
  info: 'pending',
  informational: 'pending',
  suppressed: 'cancelled',
  cancelled: 'cancelled',
  canceled: 'cancelled',
  skipped: 'cancelled',
}

const PILL_KEYS = new Set(['pending', 'running', 'success', 'failed', 'timeout', 'cancelled'])

export function opsStatusPillModifier(status: string | null | undefined): string {
  const raw = String(status || '').trim().toLowerCase().replace(/[\s-]+/g, '_')
  if (!raw) return 'pending'
  const mapped = STATUS_ALIASES[raw] || raw
  return PILL_KEYS.has(mapped) ? mapped : 'pending'
}

export function opsStatusPillClass(status: string | null | undefined): string {
  return `hfl-ops-status-pill--${opsStatusPillModifier(status)}`
}
