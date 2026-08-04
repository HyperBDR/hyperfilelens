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

export type MinimalInstallerArtifact = {
  filename: string
  sha256: string
  size: number
}

export type MinimalInstallerManifest = {
  schema_version: number
  artifacts: Record<string, MinimalInstallerArtifact>
}

export async function fetchMinimalInstallerManifest(
  apiBase = publicApiBase(),
): Promise<MinimalInstallerManifest> {
  const base = apiBase.replace(/\/$/, '')
  const response = await fetch(`${base}/api/v1/node/enrollment/installer-metadata`, {
    cache: 'no-store',
  })
  if (!response.ok) {
    throw new Error('Minimal installer metadata is unavailable')
  }
  // Public fetch bypasses api(); still peel the standard { code, data } envelope.
  const payload = unwrapApiPayload<MinimalInstallerManifest>(await response.json())
  const expected = [
    'linux-amd64',
    'linux-arm64',
    'darwin-amd64',
    'darwin-arm64',
    'windows-amd64',
  ]
  const artifacts = payload?.artifacts
  const valid = payload?.schema_version === 1
    && artifacts
    && typeof artifacts === 'object'
    && Object.keys(artifacts).length === expected.length
    && expected.every((key) => {
      const artifact = artifacts[key]
      const extension = key.startsWith('windows-') ? 'zip' : 'tar.gz'
      const filenamePattern = new RegExp(
        `^[A-Za-z0-9._-]+/hfl-installer-${key}\\.${extension.replaceAll('.', '\\.')}$`,
      )
      return artifact
        && filenamePattern.test(artifact.filename)
        && /^[a-f0-9]{64}$/i.test(artifact.sha256)
        && Number.isSafeInteger(artifact.size)
        && artifact.size > 0
    })
  if (!valid) {
    throw new Error('Minimal installer metadata is invalid')
  }
  return payload
}

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

function shellSingleQuoted(value: string): string {
  return `'${value.replace(/'/g, `'"'"'`)}'`
}

function controlPlaneWssURL(apiBase: string): string {
  const url = new URL(apiBase)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = '/ws/node/agent/'
  url.search = ''
  url.hash = ''
  return url.toString()
}

function powershellEncodedCommand(script: string): string {
  const bytes = new Uint8Array(script.length * 2)
  for (let i = 0; i < script.length; i += 1) {
    const code = script.charCodeAt(i)
    bytes[i * 2] = code & 0xff
    bytes[i * 2 + 1] = code >> 8
  }
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return `powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand ${btoa(binary)}`
}

/**
 * Windows one-liner: pure PowerShell download + run (no curl).
 * Avoids $variables so pasting works from elevated CMD or PowerShell.
 */
function buildWindowsEnrollmentInstallCommand(params: {
  apiBase: string
  org: string
  role: NodeRole
  token: string
  tlsVerify: boolean
  artifact: MinimalInstallerArtifact
  operation: 'install' | 'gateway-install'
}): string {
  const archiveUrl = `${params.apiBase.replace(/\/$/, '')}/media/enroll-bootstrap/${params.artifact.filename}`
  const psBody = [
    '[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12',
    ...(params.tlsVerify
      ? []
      : [
          "Write-Warning 'TLS certificate verification is disabled. Use only on a trusted private network.'",
          '[Net.ServicePointManager]::ServerCertificateValidationCallback={[bool]1}',
        ]),
    '$work=Join-Path ([System.IO.Path]::GetTempPath()) ("hfl-installer-"+[guid]::NewGuid().ToString("n"))',
    'New-Item -ItemType Directory -Path $work -Force|Out-Null',
    'try {',
    '$archive=Join-Path $work "installer.zip"',
    `(New-Object Net.WebClient).DownloadFile(${psSingleQuoted(archiveUrl)},$archive)`,
    `if((Get-FileHash -Algorithm SHA256 $archive).Hash.ToLower() -ne ${psSingleQuoted(params.artifact.sha256.toLowerCase())}){throw 'Minimal installer checksum verification failed'}`,
    'Expand-Archive -LiteralPath $archive -DestinationPath $work -Force',
    `$env:HFL_ORG_KEY=${psSingleQuoted(params.org)}`,
    `$env:HFL_NODE_ROLE=${psSingleQuoted(params.role)}`,
    `$env:HFL_NODE_TOKEN=${psSingleQuoted(params.token)}`,
    `$env:HFL_API_BASE=${psSingleQuoted(params.apiBase)}`,
    `$env:HFL_WSS_URL=${psSingleQuoted(controlPlaneWssURL(params.apiBase))}`,
    `$env:HFL_INSECURE_TLS=${psSingleQuoted(params.tlsVerify ? '0' : '1')}`,
    `& (Join-Path $work 'hfl-enroll.exe') ${params.operation}`,
    'if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}',
    '} finally { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }',
  ].join(';')
  return powershellEncodedCommand(psBody)
}

function buildPosixEnrollmentInstallCommand(params: {
  apiBase: string
  org: string
  role: NodeRole
  token: string
  tlsVerify: boolean
  goos: 'linux' | 'darwin'
  artifacts: Record<string, MinimalInstallerArtifact>
  operation: 'install' | 'gateway-install'
  gatewayScope?: 'public' | 'private'
}): string {
  const amd64 = params.artifacts[`${params.goos}-amd64`]
  const arm64 = params.artifacts[`${params.goos}-arm64`]
  if (!amd64 || !arm64) throw new Error('Minimal installer metadata is incomplete')
  const tlsOptions = params.tlsVerify
    ? "--proto '=https' --tlsv1.2"
    : '-k'
  const warning = params.tlsVerify
    ? ''
    : "echo 'WARNING: TLS certificate verification is disabled. Use only on a trusted private network.' >&2\n"
  const base = params.apiBase.replace(/\/$/, '')
  const env = [
    `HFL_ORG_KEY=${shellSingleQuoted(params.org)}`,
    `HFL_NODE_ROLE=${shellSingleQuoted(params.role)}`,
    `HFL_NODE_TOKEN=${shellSingleQuoted(params.token)}`,
    `HFL_API_BASE=${shellSingleQuoted(params.apiBase)}`,
    `HFL_WSS_URL=${shellSingleQuoted(controlPlaneWssURL(params.apiBase))}`,
    `HFL_INSECURE_TLS=${params.tlsVerify ? '0' : '1'}`,
    ...(params.gatewayScope ? [`HFL_GATEWAY_SCOPE=${params.gatewayScope}`] : []),
  ].join(' ')
  return `${warning}work="$(mktemp -d /tmp/hfl-installer.XXXXXX)" && (\n  trap 'rm -rf "$work"' EXIT\n  base=${shellSingleQuoted(base)}\n  case "$(uname -m)" in\n    x86_64|amd64) file=${shellSingleQuoted(amd64.filename)}; expected=${shellSingleQuoted(amd64.sha256)} ;;\n    arm64|aarch64) file=${shellSingleQuoted(arm64.filename)}; expected=${shellSingleQuoted(arm64.sha256)} ;;\n    *) echo 'Unsupported CPU architecture.' >&2; exit 4 ;;\n  esac\n  curl ${tlsOptions} --fail --show-error --location --progress-bar "$base/media/enroll-bootstrap/$file" -o "$work/installer.tar.gz"\n  if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$work/installer.tar.gz" | awk '{print $1}')"; else actual="$(shasum -a 256 "$work/installer.tar.gz" | awk '{print $1}')"; fi\n  [ "$actual" = "$expected" ] || { echo 'Minimal installer checksum verification failed.' >&2; exit 3; }\n  tar -xzf "$work/installer.tar.gz" -C "$work"\n  if [ "$(id -u)" -eq 0 ]; then\n    env ${env} "$work/hfl-enroll" ${params.operation}\n  elif command -v sudo >/dev/null 2>&1; then\n    sudo env ${env} "$work/hfl-enroll" ${params.operation}\n  else\n    echo 'Administrator privileges are required. Re-run as root or install sudo.' >&2\n    exit 1\n  fi\n)`
}

/** One-liner for target host (curl pipe / download + run). Shown on deploy pages only. */
export function buildEnrollmentInstallCommand(params: {
  org: string
  role: NodeRole
  token: string
  apiBase?: string
  os: EnrollmentOs
  tlsVerify?: boolean
  manifest: MinimalInstallerManifest
}): string {
  const tlsVerify = params.tlsVerify !== false
  if (params.os === 'windows') {
    const artifact = params.manifest.artifacts['windows-amd64']
    if (!artifact) throw new Error('Windows minimal installer metadata is unavailable')
    return buildWindowsEnrollmentInstallCommand({
      apiBase: params.apiBase ?? publicApiBase(),
      org: params.org,
      role: params.role,
      token: params.token,
      tlsVerify,
      artifact,
      operation: 'install',
    })
  }
  return buildPosixEnrollmentInstallCommand({
    apiBase: params.apiBase ?? publicApiBase(),
    org: params.org,
    role: params.role,
    token: params.token,
    tlsVerify,
    goos: params.os === 'macos' ? 'darwin' : 'linux',
    artifacts: params.manifest.artifacts,
    operation: 'install',
  })
}

/** One-liner for Data Gateway host (Linux): installs agent + LensNode sidecar. */
export function buildGatewayEnrollmentInstallCommand(params: {
  org: string
  token: string
  apiBase?: string
  tlsVerify?: boolean
  manifest: MinimalInstallerManifest
  gatewayScope: 'public' | 'private'
}): string {
  return buildPosixEnrollmentInstallCommand({
    apiBase: params.apiBase ?? publicApiBase(),
    org: params.org,
    role: 'gateway',
    token: params.token,
    tlsVerify: params.tlsVerify !== false,
    goos: 'linux',
    artifacts: params.manifest.artifacts,
    operation: 'gateway-install',
    gatewayScope: params.gatewayScope,
  })
}

/** Create gateway token + build copy-paste install command. */
export async function issueGatewayEnrollmentInstall(params: {
  note?: string
  orgKey?: string
}): Promise<{ token: string; tokenId: number; command: string; tlsVerify: boolean; expiresAt: string | null }> {
  const org = params.orgKey || orgKey()
  if (!org) {
    throw new Error('Missing organization key')
  }
  const manifest = await fetchMinimalInstallerManifest()
  const row = await createNodeToken({
    role: 'gateway',
    note: params.note ?? 'deploy:gateway',
  })
  let command: string
  try {
    command = buildGatewayEnrollmentInstallCommand({
      org,
      token: row.token,
      tlsVerify: row.tls_verify,
      manifest,
      gatewayScope: 'private',
    })
  } catch (error) {
    await revokeEnrollmentToken(row.id).catch(() => undefined)
    throw error
  }
  return {
    token: row.token,
    tokenId: row.id,
    command,
    tlsVerify: row.tls_verify,
    expiresAt: row.expires_at ?? null,
  }
}

export async function issuePlatformGatewayEnrollmentInstall(params?: {
  note?: string
}): Promise<{
  token: string
  tokenId: number
  command: string
  tlsVerify: boolean
  expiresAt: string | null
}> {
  const manifest = await fetchMinimalInstallerManifest()
  const raw = await api<unknown>('/api/v1/platform-ops/lens/gateways/enrollment', {
    method: 'POST',
    body: JSON.stringify({
      note: params?.note ?? 'deploy:platform-gateway',
    }),
  })
  const payload = unwrapApiPayload<{
    token: string
    token_id: number
    org_key: string
    api_base: string
    tls_verify: boolean
    expires_at?: string | null
  }>(raw)
  try {
    if (
      !payload.token ||
      !payload.org_key ||
      !payload.api_base ||
      typeof payload.tls_verify !== 'boolean'
    ) {
      throw new Error('Public Data Gateway enrollment response is incomplete')
    }
    return {
      token: payload.token,
      tokenId: payload.token_id,
      command: buildGatewayEnrollmentInstallCommand({
        org: payload.org_key,
        token: payload.token,
        apiBase: payload.api_base,
        tlsVerify: payload.tls_verify,
        manifest,
        gatewayScope: 'public',
      }),
      tlsVerify: payload.tls_verify,
      expiresAt: payload.expires_at ?? null,
    }
  } catch (error) {
    if (Number.isInteger(payload.token_id) && payload.token_id > 0) {
      await revokePlatformGatewayEnrollment(payload.token_id).catch(() => undefined)
    }
    throw error
  }
}

export async function revokePlatformGatewayEnrollment(tokenId: number): Promise<void> {
  await api(`/api/v1/platform-ops/lens/gateways/enrollment/${tokenId}`, {
    method: 'DELETE',
  })
}

export async function revokeEnrollmentToken(tokenId: number): Promise<void> {
  await api(`/api/v1/node/node-tokens/${tokenId}/`, { method: 'DELETE' })
}

export async function auditPlatformGatewayEnrollmentCopy(tokenId: number): Promise<void> {
  await api(`/api/v1/platform-ops/lens/gateways/enrollment/${tokenId}/copied`, {
    method: 'POST',
  })
}

/** Create token + build copy-paste install command (does not download script body). */
export async function issueEnrollmentInstall(params: {
  role: NodeRole
  os: EnrollmentOs
  note?: string
}): Promise<{ token: string; tokenId: number; command: string; tlsVerify: boolean; expiresAt: string | null }> {
  const org = orgKey()
  if (!org) {
    throw new Error('Missing organization key')
  }
  const manifest = await fetchMinimalInstallerManifest()
  const row = await createNodeToken({ role: params.role, note: params.note })
  let command: string
  try {
    command = buildEnrollmentInstallCommand({
      org,
      role: params.role,
      token: row.token,
      os: params.os,
      tlsVerify: row.tls_verify,
      manifest,
    })
  } catch (error) {
    await revokeEnrollmentToken(row.id).catch(() => undefined)
    throw error
  }
  return {
    token: row.token,
    tokenId: row.id,
    command,
    tlsVerify: row.tls_verify,
    expiresAt: row.expires_at ?? null,
  }
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
