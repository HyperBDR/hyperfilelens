/* HFL-owned runtime Sentry adapter for the bundled SourceLens UI. */
(function initializeBundledSourceLensSentry() {
  'use strict'

  var config = window.__HFL_SOURCELENS_SENTRY__ || {}
  if (!config.enabled || !config.dsn || !config.environment || !config.release) return

  var dsn
  try {
    dsn = new URL(config.dsn)
  } catch (_error) {
    console.warn('[hfl-sentry] Invalid bundled SourceLens DSN; reporting is disabled.')
    return
  }
  var path = dsn.pathname.replace(/\/+$/, '').split('/')
  var projectId = path.pop()
  var publicKey = dsn.username
  if (!/^https?:$/.test(dsn.protocol) || !/^\d+$/.test(projectId || '')
    || !publicKey || dsn.password || dsn.search || dsn.hash) return
  var prefix = path.join('/')
  var sentrySaas = dsn.hostname === 'sentry.io' || dsn.hostname.endsWith('.sentry.io')
  var loaderUrl = sentrySaas
    ? 'https://js.sentry-cdn.com/' + encodeURIComponent(publicKey) + '.min.js'
    : dsn.origin + prefix + '/js-sdk-loader/' + encodeURIComponent(publicKey) + '.min.js'

  function safeOrigin(value) {
    try {
      return new URL(value, window.location.origin).origin
    } catch (_error) {
      return undefined
    }
  }

  function sanitizeSpan(span) {
    var safe = { data: {} }
    var fields = [
      'is_segment', 'op', 'origin', 'parent_span_id', 'same_process_as_parent',
      'segment_id', 'span_id', 'start_timestamp', 'status', 'timestamp', 'trace_id'
    ]
    fields.forEach(function retainSafeSpanField(key) {
      var value = span[key]
      if (['boolean', 'number', 'string'].indexOf(typeof value) !== -1) safe[key] = value
    })
    return safe
  }

  function sanitizeTraceContext(value) {
    if (!value || typeof value !== 'object') return undefined
    var safe = { data: {} }
    var fields = ['op', 'origin', 'parent_span_id', 'span_id', 'status', 'trace_id']
    fields.forEach(function retainSafeTraceField(key) {
      if (typeof value[key] === 'string') safe[key] = value[key]
    })
    return typeof safe.trace_id === 'string' && typeof safe.span_id === 'string'
      ? safe
      : undefined
  }

  function beforeSend(event) {
    delete event.user
    delete event.message
    delete event.logentry
    delete event.extra
    delete event.fingerprint
    var traceContext = sanitizeTraceContext(event.contexts && event.contexts.trace)
    event.contexts = traceContext ? { trace: traceContext } : undefined
    if (event.request) {
      var origin = safeOrigin(event.request.url)
      event.request = { headers: {} }
      if (origin) event.request.url = origin
    }
    delete event.transaction
    delete event.transaction_info
    if (event.spans) event.spans = event.spans.map(sanitizeSpan)
    if (event.breadcrumbs) {
      event.breadcrumbs = event.breadcrumbs.map(function sanitizeBreadcrumb(crumb) {
        return {
          category: crumb.category,
          level: crumb.level,
          timestamp: crumb.timestamp,
          type: crumb.type
        }
      })
    }
    var exceptions = event.exception && event.exception.values || []
    exceptions.forEach(function sanitizeException(exception) {
      if (exception.value) exception.value = '[Filtered]'
      if (exception.mechanism) delete exception.mechanism.data
      var frames = exception.stacktrace && exception.stacktrace.frames || []
      frames.forEach(function sanitizeFrame(frame) { delete frame.vars })
    })
    event.tags = {
      component: 'sourcelens-frontend',
      deployment_mode: 'bundled',
      product: 'hyperfilelens'
    }
    return event
  }

  window.sentryOnLoad = function configureSentry() {
    try {
      var options = {
        dsn: config.dsn,
        environment: config.environment,
        release: config.release,
        tracesSampleRate: Number(config.tracesSampleRate) || 0,
        sendDefaultPii: false,
        beforeSend: beforeSend,
        beforeSendTransaction: beforeSend,
        beforeSendSpan: sanitizeSpan,
        initialScope: {
          tags: {
            product: 'hyperfilelens',
            component: 'sourcelens-frontend',
            deployment_mode: 'bundled'
          }
        }
      }
      window.Sentry.init(options)
    } catch (error) {
      console.warn('[hfl-sentry] Bundled SourceLens initialization failed.', error)
    }
  }

  var script = document.createElement('script')
  script.async = true
  script.crossOrigin = 'anonymous'
  script.src = loaderUrl
  script.dataset.hflSentryLoader = 'true'
  script.onerror = function sentryLoaderFailed() {
    console.warn('[hfl-sentry] Sentry loader is unavailable; SourceLens will continue.')
  }
  document.head.appendChild(script)
})()
