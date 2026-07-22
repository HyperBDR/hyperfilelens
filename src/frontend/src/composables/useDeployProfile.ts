export interface DeployProfile {
  site_role: 'tenant' | 'ops'
  email_signup_enabled: boolean
  platform_ops_enabled: boolean
  password_reset_available: boolean
  tenant_public_url: string
  admin_console_url: string
  landing_path: string
  admin_console_entry_visible: boolean
  platform_ops_access_allowed: boolean
  is_staff?: boolean
  support_org_key?: string | null
}

export const PLATFORM_OPS_LANDING_PATH = '/platform-ops/overview'

let cachedProfile: DeployProfile | null = null
let inflight: Promise<DeployProfile | null> | null = null

function parseDeployProfilePayload(raw: unknown): DeployProfile | null {
  if (!raw || typeof raw !== 'object') return null
  const outer = raw as Record<string, unknown>
  const inner = outer.data
  if (inner && typeof inner === 'object' && 'site_role' in (inner as object)) {
    return inner as DeployProfile
  }
  if ('site_role' in outer) {
    return outer as DeployProfile
  }
  return null
}

export async function fetchDeployProfile(force = false): Promise<DeployProfile | null> {
  if (!force && cachedProfile) return cachedProfile
  if (inflight) return inflight

  inflight = (async () => {
    try {
      const res = await fetch('/api/v1/meta/deploy-profile', { credentials: 'include' })
      if (!res.ok) return null
      const payload = parseDeployProfilePayload(await res.json())
      cachedProfile = payload
      return payload
    } catch {
      return null
    } finally {
      inflight = null
    }
  })()

  return inflight
}

export function getCachedDeployProfile(): DeployProfile | null {
  return cachedProfile
}

export function clearDeployProfileCache(): void {
  cachedProfile = null
}

export function shouldForceDeployProfileRefresh(
  toPath: string,
  fromPath: string,
  requiresPlatformOps = false,
): boolean {
  const targetsPlatformOps = toPath.startsWith('/platform-ops') || requiresPlatformOps
  return targetsPlatformOps && !fromPath.startsWith('/platform-ops')
}

export function platformOpsEntryUrl(adminConsoleUrl: string): string {
  const origin = adminConsoleUrl.trim().replace(/\/+$/, '')
  return origin ? `${origin}${PLATFORM_OPS_LANDING_PATH}` : ''
}

/** Resolve the deployment-specific post-login landing page. */
export async function resolvePostLoginPath(): Promise<string> {
  const profile = await fetchDeployProfile(true)
  const path = profile?.landing_path?.trim()
  return path && path.startsWith('/') ? path : '/'
}
