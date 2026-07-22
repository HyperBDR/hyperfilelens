import { api } from '../../lib/api'
import { unwrapApiPayload } from '../../lib/parse'

export interface PlatformOpsUser {
  id: number
  username: string
  email: string
  first_name?: string
  last_name?: string
  display_name: string
  is_active: boolean
  is_staff: boolean
  account_type: 'customer' | 'administrator'
  date_joined?: string | null
  last_login?: string | null
  registered_at?: string | null
  last_login_ip?: string
  has_usable_password?: boolean
  membership_count?: number
  organization?: PlatformOpsUserOrganization | null
  memberships?: PlatformOpsMembership[]
}

export interface PlatformOpsUserOrganization {
  id: number
  key: string
  name: string
  is_active: boolean
}

export interface PlatformOpsUserStats {
  total: number
  active: number
  inactive: number
  never_signed_in: number
}

export interface PlatformOpsMembership {
  id: number
  organization: number
  organization_key: string
  organization_name: string
  role: string
  is_active: boolean
  created_at?: string
}

export interface PlatformOpsUserListResponse {
  count: number
  page: number
  page_size: number
  results: PlatformOpsUser[]
  stats: PlatformOpsUserStats
}

export interface PlatformOpsOrganization {
  id: number
  key: string
  name: string
  is_active: boolean
  owner_email?: string | null
  owner_user_id?: number | null
  owner_display_name?: string
  member_count?: number
  node_count?: number
  failed_task_count?: number
  incident_count?: number
  created_at?: string | null
  updated_at?: string | null
}

export interface PlatformOpsOrganizationStats {
  total: number
  active: number
  inactive: number
  with_incidents: number
}

export interface PlatformOpsOrganizationListResponse {
  count: number
  page: number
  page_size: number
  results: PlatformOpsOrganization[]
  stats: PlatformOpsOrganizationStats
}

export async function listPlatformOpsUsers(params: {
  page?: number
  page_size?: number
  search?: string
  status?: string
  account_type?: string
}): Promise<PlatformOpsUserListResponse> {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  if (params.search?.trim()) qs.set('search', params.search.trim())
  if (params.status) qs.set('status', params.status)
  if (params.account_type) qs.set('account_type', params.account_type)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  const raw = await api<unknown>(`/api/v1/platform-ops/users${suffix}`)
  return unwrapApiPayload<PlatformOpsUserListResponse>(raw)
}

export async function getPlatformOpsUser(id: number): Promise<PlatformOpsUser> {
  const raw = await api<unknown>(`/api/v1/platform-ops/users/${id}`)
  return unwrapApiPayload<PlatformOpsUser>(raw)
}

export async function createPlatformOpsUser(body: {
  email: string
  password: string
  first_name?: string
  last_name?: string
  is_active?: boolean
  is_staff?: boolean
  organization_name?: string
}): Promise<PlatformOpsUser> {
  const raw = await api<unknown>('/api/v1/platform-ops/users', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  return unwrapApiPayload<PlatformOpsUser>(raw)
}

export async function updatePlatformOpsUser(
  id: number,
  body: Partial<{
    email: string
    first_name: string
    last_name: string
    is_active: boolean
    is_staff: boolean
  }>,
): Promise<PlatformOpsUser> {
  const raw = await api<unknown>(`/api/v1/platform-ops/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
  return unwrapApiPayload<PlatformOpsUser>(raw)
}

export async function resetPlatformOpsUserPassword(id: number, password: string): Promise<void> {
  await api(`/api/v1/platform-ops/users/${id}/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ password }),
  })
}

export async function deletePlatformOpsUsers(ids: number[]): Promise<void> {
  await Promise.all(ids.map((id) => api(`/api/v1/platform-ops/users/${id}`, { method: 'DELETE' })))
}

export async function listPlatformOpsOrganizations(params: {
  page?: number
  page_size?: number
  search?: string
  status?: string
  health?: string
}): Promise<PlatformOpsOrganizationListResponse> {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  if (params.search?.trim()) qs.set('search', params.search.trim())
  if (params.status) qs.set('status', params.status)
  if (params.health) qs.set('health', params.health)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  const raw = await api<unknown>(`/api/v1/platform-ops/orgs${suffix}`)
  return unwrapApiPayload<PlatformOpsOrganizationListResponse>(raw)
}

export async function getPlatformOpsOrganization(
  id: number,
  options?: { signal?: AbortSignal },
): Promise<PlatformOpsOrganization> {
  const raw = await api<unknown>(`/api/v1/platform-ops/orgs/${id}`, {
    signal: options?.signal,
  })
  return unwrapApiPayload<PlatformOpsOrganization>(raw)
}
