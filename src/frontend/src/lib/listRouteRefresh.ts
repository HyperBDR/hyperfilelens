/** Query flag: list pages reload when returning from add/deploy flows. */
export const LIST_ROUTE_REFRESH_KEY = '_listRefresh'

export function routeLocationWithListRefresh(target: string) {
  const [path, search = ''] = target.split('?')
  const query: Record<string, string> = {}
  new URLSearchParams(search).forEach((value, key) => {
    query[key] = value
  })
  query[LIST_ROUTE_REFRESH_KEY] = String(Date.now())
  return { path, query }
}

export function stripListRefreshQuery(query: Record<string, unknown>): Record<string, string> {
  const next: Record<string, string> = {}
  for (const [key, value] of Object.entries(query)) {
    if (key === LIST_ROUTE_REFRESH_KEY || value == null) continue
    if (Array.isArray(value)) {
      if (value[0] != null) next[key] = String(value[0])
    } else {
      next[key] = String(value)
    }
  }
  return next
}
