/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_SHOW_EULA?: string
  readonly SENTRY_ENABLED?: string
  readonly SENTRY_DSN?: string
  readonly SENTRY_ENVIRONMENT?: string
  readonly SENTRY_RELEASE?: string
  readonly SENTRY_TRACES_SAMPLE_RATE?: string
  readonly SENTRY_SEND_DEFAULT_PII?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
