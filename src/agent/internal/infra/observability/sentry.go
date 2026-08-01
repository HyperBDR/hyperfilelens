// Package observability provides optional, privacy-safe Agent error reporting.
package observability

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/getsentry/sentry-go"
)

const flushTimeout = 2 * time.Second

func enabled() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("SENTRY_ENABLED"))) {
	case "1", "true", "yes", "on":
		return true
	default:
		return false
	}
}

func sampleRate() float64 {
	value, err := strconv.ParseFloat(strings.TrimSpace(os.Getenv("SENTRY_TRACES_SAMPLE_RATE")), 64)
	if err != nil || value < 0 || value > 1 {
		return 0
	}
	return value
}

// Initialize enables Sentry for an explicitly configured Platform Gateway Agent.
// It returns a shutdown function that flushes pending events without blocking exit.
func Initialize() func() {
	if !enabled() {
		return func() {}
	}
	dsn := strings.TrimSpace(os.Getenv("SENTRY_BACKEND_DSN"))
	if dsn == "" {
		_, _ = fmt.Fprintln(os.Stderr, "[sentry] backend DSN is missing; Agent reporting is disabled")
		return func() {}
	}
	err := sentry.Init(sentry.ClientOptions{
		Dsn:              dsn,
		Environment:      strings.TrimSpace(os.Getenv("SENTRY_ENVIRONMENT")),
		Release:          strings.TrimSpace(os.Getenv("SENTRY_RELEASE")),
		ServerName:       "hfl-platform-gateway",
		EnableTracing:    sampleRate() > 0,
		TracesSampleRate: sampleRate(),
		SendDefaultPII:   false,
		AttachStacktrace: true,
		MaxBreadcrumbs:   20,
		BeforeSend: func(event *sentry.Event, _ *sentry.EventHint) *sentry.Event {
			event.User = sentry.User{}
			event.ServerName = "hfl-platform-gateway"
			delete(event.Contexts, "device")
			if event.Tags == nil {
				event.Tags = map[string]string{}
			}
			event.Tags["product"] = "hyperfilelens"
			event.Tags["component"] = "hfl-agent"
			event.Tags["gateway_type"] = "platform"
			return event
		},
	})
	if err != nil {
		_, _ = fmt.Fprintf(os.Stderr, "[sentry] Agent initialization failed; continuing: %v\n", err)
		return func() {}
	}
	return func() { sentry.Flush(flushTimeout) }
}

// CaptureException reports an unrecoverable daemon failure without its payload.
func CaptureException(err error) {
	if err != nil {
		sentry.CaptureMessage("Platform Gateway Agent exited unexpectedly")
	}
}

// RecoverPanic reports a process panic, flushes it, and preserves panic semantics.
func RecoverPanic() {
	if recovered := recover(); recovered != nil {
		sentry.CaptureMessage("Platform Gateway Agent panicked")
		sentry.Flush(flushTimeout)
		panic(recovered)
	}
}
