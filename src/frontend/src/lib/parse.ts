/** Peel nested platform `{ code, message, data }` response layers (up to 6 deep). */
export function unwrapApiPayload<T = unknown>(payload: unknown): T {
  let cur: unknown = payload
  for (let depth = 0; depth < 6; depth++) {
    if (cur == null || typeof cur !== 'object') break
    const o = cur as Record<string, unknown>
    if ('body' in o && o.body != null) {
      cur = o.body
      continue
    }
    const looksLikeEnvelope = 'data' in o && ('code' in o || 'message' in o)
    if (looksLikeEnvelope && o.data !== undefined) {
      cur = o.data
      continue
    }
    break
  }
  return cur as T
}

/** @deprecated Use {@link unwrapApiPayload} */
export function unwrapApiRecord<T>(data: unknown): T {
  return unwrapApiPayload<T>(data)
}

/** Read enrollment token from create-token API payloads (handles envelope + field aliases). */
export function extractEnrollmentToken(payload: unknown): string {
  const row = unwrapApiPayload<Record<string, unknown>>(payload)
  if (!row || typeof row !== 'object') return ''
  const raw = row.token ?? row.enrollmentToken ?? row.enrollment_token
  if (typeof raw !== 'string') return ''
  const token = raw.trim()
  if (!token || token === 'undefined' || token === 'null') return ''
  return token
}

function listFromRecord<T>(o: Record<string, unknown>): T[] | null {
  if (Array.isArray(o.results)) return o.results as T[]
  if (Array.isArray(o.list)) return o.list as T[]
  if (Array.isArray(o.items)) return o.items as T[]
  return null
}

export type ApiPaginationMeta = {
  total: number
  page: number
  pageSize: number
  next?: string | null
  previous?: string | null
}

/** @deprecated Prefer {@link ApiPaginationMeta} */
export type PaginationMeta = ApiPaginationMeta

function normalizePagination(p: Record<string, unknown>): ApiPaginationMeta {
  return {
    total: Number(p.total) || 0,
    page: Number(p.page) || 1,
    pageSize: Number(p.pageSize ?? p.page_size) || 10,
    next: (p.next as string | null | undefined) ?? null,
    previous: (p.previous as string | null | undefined) ?? null,
  }
}

function paginationFromRecord(o: Record<string, unknown>): ApiPaginationMeta | null {
  const p = o.pagination
  if (p && typeof p === 'object') return normalizePagination(p as Record<string, unknown>)
  return null
}

/** Read pagination from `{ data: { list, pagination } }` or top-level `pagination`. */
export function asPagination(data: unknown): ApiPaginationMeta | null {
  if (!data || typeof data !== 'object') return null
  const o = data as Record<string, unknown>

  const direct = paginationFromRecord(o)
  if (direct) return direct

  const inner = o.data
  if (inner && typeof inner === 'object' && !Array.isArray(inner)) {
    return paginationFromRecord(inner as Record<string, unknown>)
  }

  return null
}

/** Unwrap a single object from `{ code, data: { ... } }` or a plain record. */
export function asObject<T extends Record<string, unknown> = Record<string, unknown>>(
  data: unknown,
): T | null {
  if (!data || typeof data !== 'object') return null
  if (Array.isArray(data)) return null
  const o = data as Record<string, unknown>
  const inner = o.data
  if (inner && typeof inner === 'object' && !Array.isArray(inner)) {
    const record = inner as Record<string, unknown>
    if ('list' in record || 'pagination' in record) return null
    return inner as T
  }
  return o as T
}

/** Normalize list payloads from DRF (array, `results`, or `{ data: { list, pagination } }`). */
export function asList<T = unknown>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[]
  if (!data || typeof data !== 'object') return []
  const o = data as Record<string, unknown>

  const direct = listFromRecord<T>(o)
  if (direct) return direct

  if (Array.isArray(o.data)) return o.data as T[]

  const inner = o.data
  if (inner && typeof inner === 'object' && !Array.isArray(inner)) {
    const nested = listFromRecord<T>(inner as Record<string, unknown>)
    if (nested) return nested
  }

  return []
}
