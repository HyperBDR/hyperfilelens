import { getEffectiveOrgKey } from '../composables/useAuth'
import { api } from './api'
import { asList, extractEnrollmentToken, unwrapApiPayload } from './parse'
import { publishedAgentVersionLabel } from './agentVersion'
import type {
  NodeLifecycleKind,
  NodeOperationBatchPreview,
  NodeOperationBatchStartResult,
  NodeOperationStartResult,
} from '../types/nodeLifecycle'
import type { ApiNode, ApiNodeToken, CreateNodeTokenBody, NodeRole, NodeStatus, UpdateNodeBody } from '../types/node'

const API_BASE = import.meta.env.VITE_API_BASE?.toString() || ''

function orgKey(): string {
  return getEffectiveOrgKey()
}

/** Public API origin for enrollment scripts (same host as the console). */
export function publicApiBase(): string {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin.replace(/\/$/, '')
  }
  return API_BASE.replace(/\/$/, '')
}

export async function listAllNodes(
  params?: { role?: NodeRole; status?: NodeStatus },
  init?: RequestInit,
): Promise<ApiNode[]> {
  const qs = new URLSearchParams()
  if (params?.role) qs.set('role', params.role)
  if (params?.status) qs.set('status', params.status)
  const path = qs.toString() ? `/api/v1/node/nodes/?${qs.toString()}` : '/api/v1/node/nodes/'
  const data = await api<unknown>(path, init)
  return asList<ApiNode>(data)
}

export async function listNodesPaged(
  params: {
    role?: NodeRole
    status?: NodeStatus
    page?: number
    page_size?: number
    search?: string
    search_field?: string
  },
  init?: RequestInit,
): Promise<{ count: number; results: ApiNode[] }> {
  const qs = new URLSearchParams()
  if (params.role) qs.set('role', params.role)
  if (params.status) qs.set('status', params.status)
  if (params.search?.trim()) qs.set('search', params.search.trim())
  if (params.search_field?.trim()) qs.set('search_field', params.search_field.trim())
  qs.set('page', String(params.page ?? 1))
  qs.set('page_size', String(params.page_size ?? 30))
  const path = `/api/v1/node/nodes/?${qs.toString()}`
  const data = await api<unknown>(path, init)
  const raw = unwrapApiPayload<Record<string, unknown>>(data)
  return {
    count: typeof raw.count === 'number' ? raw.count : asList<ApiNode>(raw).length,
    results: asList<ApiNode>(raw),
  }
}

/** @deprecated Prefer {@link listAllNodes} or {@link listNodesPaged}. */
export async function listNodes(
  params?: { role?: NodeRole; status?: NodeStatus; page?: number; page_size?: number; search?: string; search_field?: string },
  init?: RequestInit,
): Promise<ApiNode[]> {
  if (params?.page_size != null || params?.page != null) {
    const paged = await listNodesPaged(
      {
        role: params.role,
        status: params.status,
        page: params.page,
        page_size: params.page_size,
        search: params.search,
        search_field: params.search_field,
      },
      init,
    )
    return paged.results
  }
  return listAllNodes(params, init)
}

export async function getNode(nodeId: number, init?: RequestInit): Promise<ApiNode> {
  const raw = await api<unknown>(`/api/v1/node/nodes/${nodeId}/`, init)
  return unwrapApiPayload<ApiNode>(raw)
}


export type NodeBindingsRepository = {
  id: number
  name: string
  status: string
  health: string
  config?: Record<string, unknown>
  nas_protocol?: string | null
  capacity_bytes?: number
  estimated_usage_bytes?: number
}

export type NodeBindingsSourceNas = {
  id: number
  name: string
  resource_type: string
  mount_status?: string
  mount_point?: string
  status?: string
  config?: Record<string, unknown>
}

export type NodeBindings = {
  proxy_id: number
  target_nas_repositories: NodeBindingsRepository[]
  standalone_disk_repositories: NodeBindingsRepository[]
  source_nas_resources: NodeBindingsSourceNas[]
  totals: {
    target_nas_repositories: number
    standalone_disk_repositories: number
    source_nas_resources: number
  }
}

export async function getNodeBindings(nodeId: number, init?: RequestInit): Promise<NodeBindings> {
  const raw = await api<unknown>(`/api/v1/node/nodes/${nodeId}/bindings/`, init)
  return unwrapApiPayload<NodeBindings>(raw)
}

export async function updateNode(nodeId: number, body: UpdateNodeBody): Promise<ApiNode> {
  const raw = await api<unknown>(`/api/v1/node/nodes/${nodeId}/`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
  return unwrapApiPayload<ApiNode>(raw)
}

export const NODE_LIFECYCLE_MAX_CONCURRENT = 5
export type NodeLifecycleScope = 'tenant' | 'platform'

function nodeLifecyclePath(scope: NodeLifecycleScope, relative: string): string {
  const clean = relative.replace(/^\/+|\/+$/g, '')
  if (scope === 'platform') {
    return `/api/v1/platform-ops/lens/gateways/${clean}`
  }
  return `/api/v1/node/nodes/${clean}/`
}

export class NodeLifecycleApiError extends Error {
  code: string
  blockers?: Array<Record<string, unknown>>

  constructor(message: string, code: string, blockers?: Array<Record<string, unknown>>) {
    super(message)
    this.name = 'NodeLifecycleApiError'
    this.code = code
    this.blockers = blockers
  }
}

function parseLifecycleError(raw: unknown): NodeLifecycleApiError {
  const payload = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const message = String(payload.error || payload.detail || 'Operation failed')
  const code = String(payload.code || 'lifecycle_rejected')
  const blockers = Array.isArray(payload.blockers) ? payload.blockers : undefined
  return new NodeLifecycleApiError(message, code, blockers)
}

async function postLifecycle<T>(path: string, body: unknown): Promise<T> {
  try {
    const raw = await api<unknown>(path, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    return unwrapApiPayload<T>(raw)
  } catch (e) {
    const err = e as { detail?: unknown; message?: string }
    const payload = err?.detail ?? e
    if (payload && typeof payload === 'object') {
      throw parseLifecycleError(payload)
    }
    throw e
  }
}

export async function startNodeOperation(
  nodeId: number,
  kind: NodeLifecycleKind,
  options?: { force?: boolean; scope?: NodeLifecycleScope },
): Promise<NodeOperationStartResult> {
  return postLifecycle(nodeLifecyclePath(options?.scope ?? 'tenant', `${nodeId}/operations`), {
    kind,
    force: Boolean(options?.force),
  })
}

export async function previewNodeOperationsBatch(params: {
  kind: NodeLifecycleKind
  nodeIds: number[]
  maxConcurrent?: number
  scope?: NodeLifecycleScope
}): Promise<NodeOperationBatchPreview> {
  return postLifecycle(nodeLifecyclePath(params.scope ?? 'tenant', 'operations/preview'), {
    kind: params.kind,
    node_ids: params.nodeIds,
    max_concurrent: params.maxConcurrent ?? NODE_LIFECYCLE_MAX_CONCURRENT,
  })
}

export async function startNodeOperationsBatch(params: {
  kind: NodeLifecycleKind
  nodeIds: number[]
  maxConcurrent?: number
  force?: boolean
  scope?: NodeLifecycleScope
}): Promise<NodeOperationBatchStartResult> {
  return postLifecycle(nodeLifecyclePath(params.scope ?? 'tenant', 'operations/batch'), {
    kind: params.kind,
    node_ids: params.nodeIds,
    max_concurrent: params.maxConcurrent ?? NODE_LIFECYCLE_MAX_CONCURRENT,
    force: Boolean(params.force),
  })
}

export type NodeLifecycleWatchEntry = Pick<
  ApiNode,
  'id' | 'status' | 'routable' | 'version' | 'lifecycle'
> & {
  is_deleted?: boolean
}

/** Poll lifecycle state for nodes in an active upgrade/remove batch (read-only). */
export async function fetchLifecycleWatch(
  nodeIds: number[],
  scope: NodeLifecycleScope = 'tenant',
): Promise<NodeLifecycleWatchEntry[]> {
  const ids = [...new Set(nodeIds.filter((id) => Number.isFinite(id) && id > 0))]
  if (ids.length === 0) return []
  const raw = await postLifecycle<{ nodes: NodeLifecycleWatchEntry[] }>(
    nodeLifecyclePath(scope, 'lifecycle-watch'),
    { node_ids: ids },
  )
  return Array.isArray(raw.nodes) ? raw.nodes : []
}

export async function deleteNode(nodeId: number): Promise<void> {
  await api<unknown>(`/api/v1/node/nodes/${nodeId}/`, { method: 'DELETE' })
}

export async function createNodeToken(body: CreateNodeTokenBody): Promise<ApiNodeToken> {
  const raw = await api<unknown>('/api/v1/node/node-tokens/', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  const token = extractEnrollmentToken(raw)
  if (!token) {
    throw new Error('Enrollment token missing in API response')
  }
  const row = unwrapApiPayload<ApiNodeToken>(raw)
  return { ...row, token }
}

export async function getNodeToken(tokenId: number): Promise<ApiNodeToken> {
  const raw = await api<unknown>(`/api/v1/node/node-tokens/${tokenId}/`)
  return unwrapApiPayload<ApiNodeToken>(raw)
}

/** Create enrollment token for deploy / install one-liners. */
export async function createEnrollmentToken(params: {
  role: NodeRole
  note?: string
}): Promise<{ token: string; tokenId: number; tlsVerify: boolean }> {
  const org = orgKey()
  if (!org) {
    throw new Error('Missing organization key')
  }
  const raw = await api<unknown>('/api/v1/node/node-tokens/', {
    method: 'POST',
    body: JSON.stringify({
      role: params.role,
      note: params.note,
    }),
  })
  const token = extractEnrollmentToken(raw)
  if (!token) {
    throw new Error('Enrollment token missing in API response')
  }
  const row = unwrapApiPayload<ApiNodeToken>(raw)
  return {
    token,
    tokenId: row.id,
    tlsVerify: typeof row.tls_verify === 'boolean' ? row.tls_verify : true,
  }
}

export type EnrollmentOs = 'linux' | 'windows' | 'macos'

export function enrollmentDownloadType(os: EnrollmentOs): string {
  if (os === 'windows') return 'windows'
  if (os === 'macos') return 'macos'
  return 'linux'
}

/** Signed download URL for platform-specific enrollment installer. */
export function buildEnrollmentDownloadUrl(params: {
  org: string
  role: NodeRole
  token: string
  apiBase?: string
  os: EnrollmentOs
}): string {
  const type = enrollmentDownloadType(params.os)
  const qs = new URLSearchParams({
    type,
    org: params.org,
    role: params.role,
    token: params.token,
    api_base: params.apiBase ?? publicApiBase(),
  })
  const base = (params.apiBase ?? publicApiBase()).replace(/\/$/, '')
  return `${base}/api/v1/node/enrollment/bootstrap?${qs.toString()}`
}

/** Data Gateway bootstrap URL (agent + LensNode sidecar, Linux only). */
export function buildGatewayEnrollmentDownloadUrl(params: {
  org: string
  token: string
  apiBase?: string
}): string {
  const qs = new URLSearchParams({
    org: params.org,
    token: params.token,
    api_base: params.apiBase ?? publicApiBase(),
  })
  const base = (params.apiBase ?? publicApiBase()).replace(/\/$/, '')
  return `${base}/api/v1/node/enrollment/bootstrap-gateway?${qs.toString()}`
}

/** Escape a URL for use inside a PowerShell single-quoted string. */
function psSingleQuoted(value: string): string {
  return `'${value.replace(/'/g, "''")}'`
}

/**
 * Windows one-liner: pure PowerShell download + run (no curl).
 * Avoids $variables so pasting works from elevated CMD or PowerShell.
 */
function buildWindowsEnrollmentInstallCommand(url: string, tlsVerify: boolean): string {
  const bootstrapPath =
    "[System.IO.Path]::Combine([System.IO.Path]::GetTempPath(),'hfl-bootstrap.ps1')"
  const psBody = [
    '[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12',
    ...(tlsVerify
      ? []
      : [
          "Write-Warning 'TLS certificate verification is disabled. Use only on a trusted private network.'",
          '[Net.ServicePointManager]::ServerCertificateValidationCallback={[bool]1}',
        ]),
    `(New-Object Net.WebClient).DownloadFile(${psSingleQuoted(url)},${bootstrapPath})`,
    `& (${bootstrapPath})`,
  ].join(';')
  return `powershell -NoProfile -ExecutionPolicy Bypass -Command "${psBody}"`
}

function buildPosixEnrollmentInstallCommand(
  url: string,
  bootstrapName: string,
  tlsVerify: boolean,
): string {
  const tlsOptions = tlsVerify
    ? "--proto '=https' --tlsv1.2"
    : '-k'
  const warning = tlsVerify
    ? ''
    : "echo 'WARNING: TLS certificate verification is disabled. Use only on a trusted private network.' >&2\n"
  return `${warning}tmp="$(mktemp /tmp/${bootstrapName}.XXXXXX)" && (\n  trap 'rm -f "$tmp"' EXIT\n  curl ${tlsOptions} --fail --show-error --location '${url}' -o "$tmp"\n  sudo bash "$tmp"\n)`
}

/** One-liner for target host (curl pipe / download + run). Shown on deploy pages only. */
export function buildEnrollmentInstallCommand(params: {
  org: string
  role: NodeRole
  token: string
  apiBase?: string
  os: EnrollmentOs
  tlsVerify?: boolean
}): string {
  const url = buildEnrollmentDownloadUrl({ ...params, os: params.os })
  const tlsVerify = params.tlsVerify !== false
  if (params.os === 'windows') {
    return buildWindowsEnrollmentInstallCommand(url, tlsVerify)
  }
  if (params.os === 'macos') {
    return buildPosixEnrollmentInstallCommand(url, 'hfl-agent-bootstrap', tlsVerify)
  }
  return buildPosixEnrollmentInstallCommand(url, 'hfl-agent-bootstrap', tlsVerify)
}

/** One-liner for Data Gateway host (Linux): installs agent + LensNode sidecar. */
export function buildGatewayEnrollmentInstallCommand(params: {
  org: string
  token: string
  apiBase?: string
  tlsVerify?: boolean
}): string {
  const url = buildGatewayEnrollmentDownloadUrl(params)
  return buildPosixEnrollmentInstallCommand(
    url,
    'hfl-gateway-bootstrap',
    params.tlsVerify !== false,
  )
}

/** Create gateway token + build copy-paste install command. */
export async function issueGatewayEnrollmentInstall(params: {
  note?: string
  orgKey?: string
}): Promise<{ token: string; tokenId: number; command: string; tlsVerify: boolean }> {
  const org = params.orgKey || orgKey()
  if (!org) {
    throw new Error('Missing organization key')
  }
  const { token, tokenId, tlsVerify } = await createEnrollmentToken({
    role: 'gateway',
    note: params.note ?? 'deploy:gateway',
  })
  const command = buildGatewayEnrollmentInstallCommand({ org, token, tlsVerify })
  return { token, tokenId, command, tlsVerify }
}

export async function issuePlatformGatewayEnrollmentInstall(params?: {
  note?: string
}): Promise<{ token: string; tokenId: number; command: string; tlsVerify: boolean }> {
  const raw = await api<unknown>('/api/v1/platform-ops/lens/gateways/enrollment', {
    method: 'POST',
    body: JSON.stringify({ note: params?.note ?? 'deploy:platform-gateway' }),
  })
  const payload = unwrapApiPayload<{
    token: string
    token_id: number
    org_key: string
    api_base: string
    tls_verify: boolean
  }>(raw)
  if (
    !payload.token ||
    !payload.org_key ||
    !payload.api_base ||
    typeof payload.tls_verify !== 'boolean'
  ) {
    throw new Error('Platform gateway enrollment response is incomplete')
  }
  return {
    token: payload.token,
    tokenId: payload.token_id,
    command: buildGatewayEnrollmentInstallCommand({
      org: payload.org_key,
      token: payload.token,
      apiBase: payload.api_base,
      tlsVerify: payload.tls_verify,
    }),
    tlsVerify: payload.tls_verify,
  }
}

/** Create token + build copy-paste install command (does not download script body). */
export async function issueEnrollmentInstall(params: {
  role: NodeRole
  os: EnrollmentOs
  note?: string
}): Promise<{ token: string; tokenId: number; command: string; tlsVerify: boolean }> {
  const org = orgKey()
  if (!org) {
    throw new Error('Missing organization key')
  }
  const { token, tokenId, tlsVerify } = await createEnrollmentToken(params)
  const command = buildEnrollmentInstallCommand({
    org,
    role: params.role,
    token,
    os: params.os,
    tlsVerify,
  })
  return { token, tokenId, command, tlsVerify }
}

import { formatAppTime } from './dateTime'

export function formatLogTime(d = new Date()): string {
  return formatAppTime(d, '')
}

export interface NodeTaskRecord {
  id: string
  status: string
  kind?: string
  result?: Record<string, unknown>
  message?: Record<string, unknown> | string
}

export function formatNodeTaskFailure(
  outcome: NodeTaskRecord & { timed_out?: boolean },
  fallback: string,
): string {
  const raw = outcome.message
  if (raw && typeof raw === 'object') {
    const err = String(raw.error || raw.message || '').trim()
    if (err) return err
  }
  if (typeof raw === 'string' && raw.trim()) return raw.trim()
  return fallback
}

/** Dispatch a runtime task to a connected Agent (WSS task.command). */
export async function dispatchNodeTask(params: {
  nodeId: number
  kind: string
  payload?: Record<string, unknown>
}): Promise<NodeTaskRecord> {
  const raw = await api<unknown>('/api/v1/node/node-tasks/', {
    method: 'POST',
    body: JSON.stringify({
      node_id: params.nodeId,
      kind: params.kind,
      payload: params.payload ?? {},
    }),
  })
  return unwrapApiPayload<NodeTaskRecord>(raw)
}

/** Poll task until terminal status or timeout. */
export async function waitForNodeTask(taskId: string, timeoutSec = 120): Promise<NodeTaskRecord & { timed_out?: boolean }> {
  const raw = await api<unknown>(`/api/v1/node/node-tasks/${taskId}/wait/?timeout=${timeoutSec}`)
  return unwrapApiPayload(raw) as NodeTaskRecord & { timed_out?: boolean }
}

export interface AgentReleaseInfo {
  version: string
  platform: string
  arch: string
  download_url: string
  expires_in?: number
}

/** Resolve signed agent package download URL (enrollment token required). */
export async function fetchAgentRelease(params: {
  role: NodeRole
  token: string
  os: EnrollmentOs
  arch?: 'amd64' | 'arm64'
}): Promise<AgentReleaseInfo> {
  const org = orgKey()
  if (!org) throw new Error('Missing organization key')
  const arch = params.arch ?? 'amd64'
  const platform = params.os === 'windows' ? 'windows' : params.os === 'macos' ? 'darwin' : 'linux'
  const qs = new URLSearchParams({
    org,
    role: params.role,
    token: params.token,
    platform,
    arch,
    api_base: publicApiBase(),
  })
  const raw = await api<unknown>(`/api/v1/node/enrollment/agent/release?${qs.toString()}`)
  const data = unwrapApiPayload<AgentReleaseInfo>(raw)
  if (!data.download_url) {
    throw new Error('Release download_url missing in API response')
  }
  return data
}

/** Published agent semver from media/agent-releases (console upgrade target). */
export async function fetchLatestAgentVersion(init?: RequestInit): Promise<string | null> {
  const raw = await api<unknown>('/api/v1/node/agent-release/latest', init)
  const data = unwrapApiPayload<{ version?: string }>(raw)
  return publishedAgentVersionLabel(data.version) || null
}

/** @deprecated Use startNodeOperation(nodeId, 'upgrade') with useNodeLifecycleOps. */
export async function upgradeNodeRemote(nodeId: number) {
  const result = await startNodeOperation(nodeId, 'upgrade')
  return { task: { id: result.task_id || result.operation_id }, outcome: { status: result.state } }
}

/** @deprecated Use startNodeOperation(nodeId, 'remove') with useNodeLifecycleOps. */
export async function removeAgentNode(nodeId: number) {
  await startNodeOperation(nodeId, 'remove')
}
