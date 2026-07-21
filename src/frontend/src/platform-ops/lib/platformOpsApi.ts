import { api, type ApiError } from '../../lib/api'
import { unwrapApiPayload } from '../../lib/parse'
import { fetchSystemMonitor, type SystemMonitorPayload } from '../../lib/monitorApi'

export type Paginated<T> = { count: number; page: number; page_size: number; results: T[] }

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  return unwrapApiPayload<T>(await api<unknown>(path, init))
}

async function send<T>(path: string, init: RequestInit): Promise<T> {
  return unwrapApiPayload<T>(await api<unknown>(path, init))
}

export async function fetchMonitoringTasks(params: Record<string, string | number | undefined>) {
  return get<Paginated<unknown>>(`/api/v1/platform-ops/monitoring/tasks${qs(params)}`)
}

export async function fetchMonitoringNodes(params: Record<string, string | number | undefined>) {
  return get<Paginated<unknown>>(`/api/v1/platform-ops/monitoring/nodes${qs(params)}`)
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
