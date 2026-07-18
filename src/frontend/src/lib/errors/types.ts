export type ProblemDetails = {
  type?: string
  title?: string
  status?: number
  code?: string
  trace_id?: string
  request_id?: string
  error_code?: string
  retryable?: boolean
  errors?: Array<{ field?: string; code?: string; message?: string }>
  meta?: Record<string, unknown>
}

export type ErrorContext =
  | { kind: 'page-load' }
  | { kind: 'drawer-load' }
  | { kind: 'mutation' }
  | { kind: 'form' }
  | { kind: 'background' }
  | { kind: 'offline' }

export type AppErrorShape = {
  status: number
  message: string
  code?: string
  errorCode?: string
  traceId?: string
  retryable?: boolean
  detail?: unknown
  fields?: Record<string, string[]>
  meta?: Record<string, unknown>
}
