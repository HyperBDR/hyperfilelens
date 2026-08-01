/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_SHOW_EULA?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface HFLAppRuntimeConfig {
  gaMeasurementId?: string
  sentryEnabled?: boolean
  sentryDsn?: string
  sentryEnvironment?: string
  sentryRelease?: string
  sentryTracesSampleRate?: number
  sentrySurface?: 'tenant' | 'admin'
}

interface Window {
  __HFL_APP_CONFIG__?: HFLAppRuntimeConfig
}
