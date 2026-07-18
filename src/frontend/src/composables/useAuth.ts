import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { router } from '../router'
import { fetchDeployProfile, resolvePostLoginPath } from './useDeployProfile'
import { getCorrelationHeaders } from '../lib/requestContext'
import { refreshAuthToken } from '../lib/authRefresh'
import { i18n } from '../i18n'

export interface User {
  id: number
  email: string
  username: string
  first_name?: string
  last_name?: string
  is_staff?: boolean
  language?: string
  timezone?: string
  access_profile?: {
    org_key: string
    role: string
    visible_features: string[]
    available_platforms: Array<{ key: string; default_path: string }>
    landing_path: string
  }
  registered_at?: string | null
  registeredAt?: string | null
}

export interface LoginError {
  errorCode?: string
  message: string
  fields?: Record<string, string[]>
}

// Auth state
const isLoggedIn = ref(false)
export const currentUser = ref<User | null>(null)
const isLoading = ref(false)

const ORG_KEY_STORAGE = 'hfl_org_key'

export function getStoredOrgKey(): string {
  try {
    return localStorage.getItem(ORG_KEY_STORAGE) || ''
  } catch {
    return ''
  }
}

export function setStoredOrgKey(orgKey: string): void {
  try {
    if (orgKey) {
      localStorage.setItem(ORG_KEY_STORAGE, orgKey)
    } else {
      localStorage.removeItem(ORG_KEY_STORAGE)
    }
  } catch {
    // ignore
  }
}

/** localStorage first, then signed-in user profile; backfills storage when profile has a key. */
export function getEffectiveOrgKey(): string {
  const stored = getStoredOrgKey()
  if (stored) return stored
  const fromProfile = currentUser.value?.access_profile?.org_key?.trim() || ''
  if (fromProfile) {
    setStoredOrgKey(fromProfile)
  }
  return fromProfile
}

// Module-level setter for use by setupAuthGuard
function setUser(userData: User | null) {
  currentUser.value = userData
  isLoggedIn.value = userData !== null
  const orgKey = userData?.access_profile?.org_key?.trim()
  if (orgKey) {
    setStoredOrgKey(orgKey)
  }
}

function parseUserPayload(data: unknown): User | null {
  if (!data || typeof data !== 'object') return null
  const o = data as Record<string, unknown>
  const payload = o.data && typeof o.data === 'object' && (o.data as Record<string, unknown>).id
    ? (o.data as User)
    : o.id
      ? (o as User)
      : null
  return payload?.id ? payload : null
}

type CurrentUserFetchResult = {
  user: User | null
  status?: number
  errorCode?: string
  refreshFailed?: boolean
}

function extractSessionErrorCode(data: unknown): string | undefined {
  if (!data || typeof data !== 'object') return undefined
  const d = data as Record<string, unknown>
  if (typeof d.code === 'string') return d.code
  if (typeof d.error_code === 'string') return d.error_code
  if (d.data && typeof d.data === 'object') {
    const inner = d.data as Record<string, unknown>
    if (typeof inner.code === 'string') return inner.code
    if (typeof inner.error_code === 'string') return inner.error_code
    if (inner.error && typeof inner.error === 'object') {
      const err = inner.error as Record<string, unknown>
      if (typeof err.code === 'string') return err.code
      if (typeof err.error_code === 'string') return err.error_code
    }
  }
  if (d.error && typeof d.error === 'object') {
    const err = d.error as Record<string, unknown>
    if (typeof err.code === 'string') return err.code
    if (typeof err.error_code === 'string') return err.error_code
  }
  return undefined
}

async function readResponseJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    return undefined
  }
}

async function fetchCurrentUserOnce(): Promise<CurrentUserFetchResult> {
  const res = await fetch('/api/v1/auth/user', {
    credentials: 'include',
    headers: getCorrelationHeaders(),
  })
  const data = await readResponseJson(res)

  if (!res.ok) {
    return {
      user: null,
      status: res.status,
      errorCode: extractSessionErrorCode(data),
    }
  }

  const payload = parseUserPayload(data)
  if (payload?.id) {
    setUser(payload)
    return { user: payload, status: res.status }
  }
  return { user: null, status: res.status }
}

async function fetchCurrentUserWithRefresh(): Promise<CurrentUserFetchResult> {
  const first = await fetchCurrentUserOnce()
  if (first.user || first.status !== 401) return first

  if (first.errorCode && SESSION_INVALID_CODES.includes(first.errorCode)) {
    return first
  }

  const refreshed = await refreshAuthToken()
  if (!refreshed.ok) {
    return {
      ...first,
      errorCode: refreshed.errorCode || first.errorCode,
      refreshFailed: true,
    }
  }

  return fetchCurrentUserOnce()
}

/** Load the signed-in user and sync org context from the backend access profile. */
export async function fetchCurrentUser(): Promise<User | null> {
  try {
    const result = await fetchCurrentUserWithRefresh()
    return result.user
  } catch {
    return null
  }
}

function hasCompleteAccessProfile(user: User | null): boolean {
  const profile = user?.access_profile
  return !!(profile?.org_key?.trim() && profile?.role?.trim())
}

// Module-level clearAuth for use by setupAuthGuard
export function clearAuth() {
  currentUser.value = null
  isLoggedIn.value = false
  isLoading.value = false
  setStoredOrgKey('')
  void import('./useDeployProfile').then(({ clearDeployProfileCache }) => {
    clearDeployProfileCache()
  })
}

// Error codes that require redirect to login
const SESSION_INVALID_CODES = [
  'OTHER_DEVICE_LOGIN',
  'PASSWORD_CHANGED',
  'ACCOUNT_DISABLED',
  'TOKEN_REUSED',
  'INVALID_TOKEN',
  'TOKEN_BLACKLISTED',
]

const WATCHDOG_INTERVAL_MS = 15_000
let sessionWatchdogTimer: number | null = null
let sessionWatchdogChecking = false
let sessionExpiredHandling = false

function isPublicSessionPath(path: string): boolean {
  return ['/login', '/register', '/auth/oauth/callback', '/auth/oauth/error'].some(publicPath => path.startsWith(publicPath))
}

async function redirectToLoginForSession(reason = 'REFRESH_EXPIRED'): Promise<void> {
  if (sessionExpiredHandling) return
  sessionExpiredHandling = true
  try {
    const currentRoute = router.currentRoute.value
    const redirect = currentRoute.fullPath || '/'

    void fetch('/api/v1/auth/logout', {
      method: 'POST',
      credentials: 'include',
      headers: getCorrelationHeaders(),
    }).catch(() => undefined)

    clearAuth()

    if (!isPublicSessionPath(currentRoute.path)) {
      await router.replace({
        path: '/login',
        query: {
          reason,
          redirect,
        },
      })
    }
  } finally {
    window.setTimeout(() => {
      sessionExpiredHandling = false
    }, 1000)
  }
}

async function checkSessionForWatchdog(): Promise<void> {
  if (sessionWatchdogChecking || !isLoggedIn.value) return
  if (isPublicSessionPath(router.currentRoute.value.path)) return
  sessionWatchdogChecking = true
  try {
    const result = await fetchCurrentUserWithRefresh()
    if (result.user) return

    if (result.errorCode && SESSION_INVALID_CODES.includes(result.errorCode)) {
      await redirectToLoginForSession(result.errorCode)
      return
    }
    if (result.status === 401 && result.refreshFailed) {
      await redirectToLoginForSession(result.errorCode || 'REFRESH_EXPIRED')
    }
  } catch {
    // Ignore transient network failures; regular API calls still handle auth errors.
  } finally {
    sessionWatchdogChecking = false
  }
}

export function useAuth() {
  const router = useRouter()

  const user = computed(() => currentUser.value)
  const loggedIn = computed(() => isLoggedIn.value)
  const loading = computed(() => isLoading.value)

  function setLoading(loading: boolean) {
    isLoading.value = loading
  }

  function handleAuthError(error: LoginError) {
    if (error.errorCode && SESSION_INVALID_CODES.includes(error.errorCode)) {
      logout()
    }
  }

  async function logout() {
    try {
      // Call logout endpoint to clear cookies
      await fetch('/api/v1/auth/logout', {
        method: 'POST',
        credentials: 'include',
        headers: getCorrelationHeaders({ 'Content-Type': 'application/json' }),
      })
    } catch {
      // Ignore errors, clear local state anyway
    } finally {
      clearAuth()
      router.push('/login')
    }
  }

  function isSessionInvalidError(errorCode?: string): boolean {
    return errorCode !== undefined && SESSION_INVALID_CODES.includes(errorCode)
  }

  function getErrorMessage(error: LoginError): string {
    const errorMessages: Record<string, string> = {
      'TOKEN_EXPIRED': i18n.global.t('login.sessionExpired'),
      'REFRESH_EXPIRED': i18n.global.t('login.sessionExpired'),
      'OTHER_DEVICE_LOGIN': i18n.global.t('login.sessionOtherDevice'),
      'PASSWORD_CHANGED': i18n.global.t('login.sessionPasswordChanged'),
      'ACCOUNT_DISABLED': i18n.global.t('login.sessionAccountDisabled'),
      'TOKEN_REUSED': i18n.global.t('login.sessionTokenReused'),
      'INVALID_TOKEN': i18n.global.t('login.sessionInvalid'),
      'TOKEN_BLACKLISTED': i18n.global.t('login.sessionInvalid'),
    }

    if (error.errorCode && errorMessages[error.errorCode]) {
      return errorMessages[error.errorCode]
    }
    return error.message
  }

  return {
    user,
    loggedIn,
    loading,
    setUser,
    setLoading,
    handleAuthError,
    logout,
    clearAuth,
    isSessionInvalidError,
    getErrorMessage,
  }
}

// Watch for router changes to check auth state
export function setupAuthGuard() {
  router.beforeEach(async (to, from, next) => {
    const publicPaths = ['/login', '/register', '/auth/oauth/callback', '/auth/oauth/error']
    const isPublicPath = publicPaths.some(path => to.path.startsWith(path))
    const isPlatformOpsPath = to.path.startsWith('/platform-ops')

    if (to.path === '/register') {
      const profile = await fetchDeployProfile()
      if (profile && !profile.registration_enabled) {
        next('/login')
        return
      }
    }

    // Check auth state for non-public paths
    if (!isPublicPath) {
      // Refresh incomplete session state (e.g. missing role after login)
      if (isLoggedIn.value && !isPlatformOpsPath && !hasCompleteAccessProfile(currentUser.value)) {
        const refreshed = await fetchCurrentUser()
        if (refreshed) {
          next()
          return
        }
        clearAuth()
        next('/login')
        return
      }

      // If already logged in with a complete profile, allow access
      if (isLoggedIn.value) {
        if (to.path === '/login') {
          next(await resolvePostLoginPath())
          return
        }
        if (isPlatformOpsPath || to.meta.requiresPlatformOps) {
          const profile = await fetchDeployProfile(true)
          const staff = currentUser.value?.is_staff === true
          if (!staff || !profile?.platform_ops_access_allowed) {
            if (profile?.tenant_public_url) {
              window.location.replace(profile.tenant_public_url)
              return
            }
            next('/login')
            return
          }
        }
        next()
        return
      }

      // Try to validate session via API
      try {
        const payload = await fetchCurrentUser()
        if (payload?.id) {
          if (isPlatformOpsPath || to.meta.requiresPlatformOps) {
            const profile = await fetchDeployProfile(true)
            const staff = payload.is_staff === true
            if (!staff || !profile?.platform_ops_access_allowed) {
              if (profile?.tenant_public_url) {
                window.location.replace(profile.tenant_public_url)
                return
              }
              next('/login')
              return
            }
          }
          next()
          return
        }

        // Invalid or no session - redirect to login
        next('/login')
        return
      } catch {
        // Network error - redirect to login
        next('/login')
        return
      }
    }

    // If logged in and going to login page, redirect to home
    if (isLoggedIn.value && to.path === '/login') {
      next(await resolvePostLoginPath())
      return
    }

    next()
  })
}

export function setupSessionWatchdog() {
  if (typeof window === 'undefined' || sessionWatchdogTimer !== null) return
  sessionWatchdogTimer = window.setInterval(() => {
    void checkSessionForWatchdog()
  }, WATCHDOG_INTERVAL_MS)

  window.addEventListener('focus', () => {
    void checkSessionForWatchdog()
  })
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) void checkSessionForWatchdog()
  })
}
