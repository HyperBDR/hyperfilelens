import { api, type ApiError } from '../../lib/api'
import { unwrapApiPayload } from '../../lib/parse'
import { fetchSystemMonitor, type SystemMonitorPayload } from '../../lib/monitorApi'

export type Paginated<T, S = never> = {
  count: number
  page: number
  page_size: number
  results: T[]
  stats?: S
}

export type PlatformOverviewMetricValue = string | number | null

export interface PlatformOverviewAlert {
  id: string
  organization_id: number
  organization_key: string
  organization_name: string
  title: string
  severity: string
  status: string
  resource_type: string
  resource_name: string
  last_triggered_at: string | null
  created_at: string
}

export interface PlatformOverviewTask {
  id: number
  task_uuid: string
  organization_id: number
  organization_key: string
  organization_name: string
  task_type: string
  status: string
  display_name: string
  error_message: string | null
  finished_at: string | null
  created_at: string
}

export interface PlatformOverviewService {
  key: string
  label: string
  status: 'healthy' | 'degraded' | 'unavailable'
  detail: string
}

export interface PlatformOverviewPayload {
  range_hours: number
  generated_at: string
  metrics: Record<string, PlatformOverviewMetricValue>
  system_health: {
    overall_status: 'healthy' | 'degraded' | 'unavailable'
    healthy_count: number
    degraded_count: number
    unavailable_count: number
    checked_at: string
    services: PlatformOverviewService[]
  }
  activity_series: Array<{
    started_at: string
    alerts: number
    failed_tasks: number
  }>
  recent_alerts: PlatformOverviewAlert[]
  recent_failed_tasks: PlatformOverviewTask[]
}

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  return unwrapApiPayload<T>(await api<unknown>(path, init))
}

async function send<T>(path: string, init: RequestInit): Promise<T> {
  return unwrapApiPayload<T>(await api<unknown>(path, init))
}

export async function fetchPlatformOverview(hours = 24) {
  return get<PlatformOverviewPayload>(`/api/v1/platform-ops/?hours=${hours}`)
}

export interface MonitoringIncident extends PlatformOverviewAlert {
  message: string
  type: string
  resource_id: string
  current_value: number | null
  threshold_value: number | null
  unit: string
  metadata: Record<string, unknown>
  first_triggered_at: string | null
  acknowledged_at: string | null
  acknowledged_by: number | null
  resolved_at: string | null
  duration_seconds: number | null
  updated_at: string
}

export type IncidentStats = {
  total: number
  firing: number
  critical: number
  acknowledged: number
  resolved: number
}

export interface MonitoringTask extends PlatformOverviewTask {
  progress: number
  current_step: string | null
  retry_count: number
  trigger_type: string
  error_code: string | null
  started_at: string | null
  updated_at: string
}

export type TaskStats = {
  total: number
  running: number
  failed: number
  timeout: number
  success_rate: number
}

export interface MonitoringNode {
  id: number
  organization_id: number
  organization_key: string
  organization_name: string
  hostname: string
  role: string
  status: string
  agent_version: string
  is_outdated: boolean
  os_name: string
  ip_address: string
  last_seen_at: string | null
  metadata: Record<string, unknown>
  updated_at: string | null
}

export type NodeStats = {
  total: number
  online: number
  offline: number
  outdated: number
  latest_version: string
}

export interface MonitoringDelivery {
  id: number
  organization_id: number
  organization_key: string
  organization_name: string
  channel_id: number
  channel_name: string
  channel_type: string
  event_type: string
  payload: Record<string, unknown>
  status: string
  error: string
  sent_at: string | null
  created_at: string
}

export type DeliveryStats = {
  total: number
  delivered: number
  failed: number
  pending: number
  delivery_rate: number
}

export async function fetchMonitoringIncidents(params: Record<string, string | number | undefined>) {
  return get<Paginated<MonitoringIncident, IncidentStats>>(
    `/api/v1/platform-ops/monitoring/alerts${qs(params)}`,
  )
}

export async function runMonitoringIncidentAction(
  incidentId: string,
  action: 'acknowledge' | 'resolve',
  note = '',
) {
  return send<MonitoringIncident>(`/api/v1/platform-ops/monitoring/alerts/${incidentId}/${action}`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

export async function fetchMonitoringTasks(params: Record<string, string | number | undefined>) {
  return get<Paginated<MonitoringTask, TaskStats>>(`/api/v1/platform-ops/monitoring/tasks${qs(params)}`)
}

export async function runMonitoringTaskAction(
  taskUuid: string,
  action: 'cancel' | 'retry',
  reason = '',
) {
  return send<MonitoringTask>(`/api/v1/platform-ops/monitoring/tasks/${taskUuid}/${action}`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

export async function fetchMonitoringNodes(params: Record<string, string | number | undefined>) {
  return get<Paginated<MonitoringNode, NodeStats>>(`/api/v1/platform-ops/monitoring/nodes${qs(params)}`)
}

export async function fetchMonitoringDeliveries(params: Record<string, string | number | undefined>) {
  return get<Paginated<MonitoringDelivery, DeliveryStats>>(
    `/api/v1/platform-ops/monitoring/notifications${qs(params)}`,
  )
}

export async function retryMonitoringDelivery(deliveryId: number) {
  return send<MonitoringDelivery>(
    `/api/v1/platform-ops/monitoring/notifications/${deliveryId}/retry`,
    { method: 'POST', body: '{}' },
  )
}

export type DeploymentHostItem = {
  id: string
  hostname: string
  name: string
  ip_address: string
  platform: string
  python_version: string
  app_version: string
  status: 'online' | 'offline'
  last_seen_at: string | null
  boot_time?: number | null
}

export async function fetchPlatformDeploymentHosts() {
  const payload = await get<{ items: DeploymentHostItem[] }>('/api/v1/platform-ops/monitoring/hosts')
  return payload.items || []
}

export function formatDeploymentHostLabel(host: DeploymentHostItem): string {
  return host.name || host.hostname || host.id
}

function shortPlatform(platform: string): string {
  const trimmed = platform.trim()
  if (!trimmed) return ''
  const withoutGlibc = trimmed.split('-with-glibc')[0]
  const withoutMicrosoft = withoutGlibc.split('-microsoft-standard-')[0]
  return withoutMicrosoft || withoutGlibc || trimmed
}

export function formatDeploymentHostDetail(host: DeploymentHostItem): string {
  const parts: string[] = []
  if (host.ip_address) parts.push(host.ip_address)
  if (host.app_version) parts.push(`v${host.app_version}`)
  else if (host.python_version) parts.push(`Py ${host.python_version}`)
  const platform = shortPlatform(host.platform)
  if (platform) parts.push(platform)
  return parts.join(' · ')
}

export function formatDeploymentHostSummary(host: DeploymentHostItem): string {
  const detail = formatDeploymentHostDetail(host)
  const label = formatDeploymentHostLabel(host)
  return detail ? `${label} · ${detail}` : label
}

export async function fetchPlatformHostMonitor(params?: {
  hours?: number
  startAt?: string
  endAt?: string
  hostId?: string
}) {
  const query: Record<string, string> = {}
  if (params?.hours !== undefined) query.hours = String(params.hours)
  if (params?.startAt) query.start_at = params.startAt
  if (params?.endAt) query.end_at = params.endAt
  if (params?.hostId) query.host_id = params.hostId
  const qs = new URLSearchParams(query).toString()
  const path = qs ? `/api/v1/platform-ops/monitoring/host?${qs}` : '/api/v1/platform-ops/monitoring/host'
  try {
    return await get<SystemMonitorPayload>(path)
  } catch (err) {
    if ((err as ApiError)?.status === 404) {
      return fetchSystemMonitor(params)
    }
    throw err
  }
}

export interface PlatformEmailSettings {
  backend: string
  host: string
  port: number
  use_tls: boolean
  use_ssl: boolean
  host_user: string
  password_configured: boolean
  password_hint: string
  from_email: string
  sources?: Record<string, string>
}

export interface PlatformIdentitySettings {
  email_signup_enabled: boolean
  self_service_password_reset: boolean
  platform_ops_enabled: boolean
  platform_ops_allowed_cidrs: string[]
  turnstile_enabled: boolean
  turnstile_site_key: string
  turnstile_secret_configured: boolean
  google_client_id: string
  google_client_secret_configured: boolean
  google_oauth_enabled: boolean
  google_oauth_redirect_uri: string
  iam: {
    registration_verification_code_minutes: number
    registration_token_expiry_hours: number
    password_reset_verification_code_minutes: number
    password_reset_timeout_seconds: number
  }
}

export interface PlatformEnvironmentSettings {
  app_version: string | null
  agent_version: string | null
  django_debug: boolean
  effective: Record<string, unknown>
  sources: Record<string, string>
  health: Record<string, unknown>
}

export async function fetchPlatformEmailSettings() {
  return get<PlatformEmailSettings>('/api/v1/platform-ops/platform/settings/email')
}

export async function patchPlatformEmailSettings(body: Record<string, unknown>) {
  return send<PlatformEmailSettings>('/api/v1/platform-ops/platform/settings/email', {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export async function testPlatformEmail(recipient: string) {
  return send<{ ok: boolean; recipient?: string; error?: string }>(
    '/api/v1/platform-ops/platform/settings/email/test',
    { method: 'POST', body: JSON.stringify({ recipient }) },
  )
}

export async function fetchPlatformIdentitySettings() {
  return get<PlatformIdentitySettings>('/api/v1/platform-ops/platform/settings/identity')
}

export async function patchPlatformIdentitySettings(body: Record<string, unknown>) {
  return send<PlatformIdentitySettings>('/api/v1/platform-ops/platform/settings/identity', {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export async function fetchPlatformEnvironment() {
  return get<PlatformEnvironmentSettings>('/api/v1/platform-ops/platform/settings/environment')
}

export async function fetchAgentReleases(params?: { page?: number; page_size?: number }) {
  return get<Record<string, unknown> & Paginated<unknown>>(
    `/api/v1/platform-ops/platform/agent-releases${qs(params || {})}`,
  )
}

export async function fetchOrgSummary(orgId: number, options?: { signal?: AbortSignal }) {
  return get<Record<string, unknown>>(
    `/api/v1/platform-ops/orgs/${orgId}/summary`,
    { signal: options?.signal },
  )
}

export async function startSupportSession(orgId: number) {
  return send<{ org_key: string; org_name: string; tenant_url: string }>(
    `/api/v1/platform-ops/orgs/${orgId}/support-session`,
    { method: 'POST' },
  )
}

export async function endSupportSession(orgId: number) {
  return send<{ ok: boolean }>(`/api/v1/platform-ops/orgs/${orgId}/support-session`, {
    method: 'DELETE',
  })
}

export async function createPlatformOrg(body: {
  key: string
  name: string
  owner_user_id: number
  is_active?: boolean
}) {
  return send<unknown>('/api/v1/platform-ops/orgs', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function updatePlatformOrg(orgId: number, body: Record<string, unknown>) {
  return send<unknown>(`/api/v1/platform-ops/orgs/${orgId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export async function deletePlatformOrgs(orgIds: number[]): Promise<void> {
  await Promise.all(orgIds.map((orgId) => api(`/api/v1/platform-ops/orgs/${orgId}`, { method: 'DELETE' })))
}

function qs(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') search.set(k, String(v))
  }
  const s = search.toString()
  return s ? `?${s}` : ''
}
