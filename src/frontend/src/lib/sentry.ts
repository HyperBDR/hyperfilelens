import * as Sentry from '@sentry/vue'
import type { App } from 'vue'
import type { Router } from 'vue-router'

const TRUTHY = new Set(['1', 'true', 'yes', 'on'])

function envBool(value: unknown, defaultValue = false): boolean {
  const raw = String(value ?? '').trim().toLowerCase()
  if (!raw) return defaultValue
  return TRUTHY.has(raw)
}

function sampleRate(value: unknown, defaultValue = 0): number {
  const parsed = Number.parseFloat(String(value ?? ''))
  if (!Number.isFinite(parsed)) return defaultValue
  return Math.max(0, Math.min(1, parsed))
}

/** Infer Sentry environment when SENTRY_ENVIRONMENT is unset (one build, pre + prod). */
export function resolveSentryEnvironment(): string {
  const configured = import.meta.env.SENTRY_ENVIRONMENT?.toString().trim()
  if (configured) return configured

  const host = window.location.hostname
  if (host === 'localhost' || host === '127.0.0.1') return 'development'
  if (/pre|staging|uat|test/i.test(host)) return 'pre'
  return 'production'
}

export function initSentry(app: App, router: Router): void {
  if (!envBool(import.meta.env.SENTRY_ENABLED)) return

  const dsn = import.meta.env.SENTRY_DSN?.toString().trim()
  if (!dsn) return

  const release = import.meta.env.SENTRY_RELEASE?.toString().trim()

  Sentry.init({
    app,
    dsn,
    environment: resolveSentryEnvironment(),
    release: release || undefined,
    integrations: [Sentry.browserTracingIntegration({ router })],
    tracesSampleRate: sampleRate(import.meta.env.SENTRY_TRACES_SAMPLE_RATE),
    sendDefaultPii: envBool(import.meta.env.SENTRY_SEND_DEFAULT_PII),
  })
}
