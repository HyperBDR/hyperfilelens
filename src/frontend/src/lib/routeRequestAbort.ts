let routeController = new AbortController()

export function beginRouteRequestScope() {
  routeController.abort()
  routeController = new AbortController()
}

export function getRouteRequestSignal(): AbortSignal {
  return routeController.signal
}
