// Package observability provides optional, privacy-safe Agent error reporting.
package observability

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/getsentry/sentry-go"
)

const flushTimeout = 2 * time.Second

// Policy is the runtime-safe subset delivered to a platform Gateway Agent.
type Policy struct {
	Enabled          bool
	BackendDSN       string
	Environment      string
	Release          string
	TracesSampleRate float64
}

var (
	policyMu      sync.Mutex
	currentPolicy Policy
	configured    bool
)

func enabled() bool {
	if !truthy(os.Getenv("HFL_SENTRY_POLICY_MANAGED")) ||
		strings.TrimSpace(strings.ToLower(os.Getenv("HFL_NODE_ROLE"))) != "gateway" {
		return false
	}
	return truthy(os.Getenv("SENTRY_ENABLED"))
}

func truthy(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
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

// Configure applies a changed server-verified policy without restarting the Agent.
func Configure(policy Policy) error {
	policy.Enabled = policy.Enabled && strings.TrimSpace(policy.BackendDSN) != ""
	policy.BackendDSN = strings.TrimSpace(policy.BackendDSN)
	policy.Environment = strings.TrimSpace(policy.Environment)
	policy.Release = strings.TrimSpace(policy.Release)
	if policy.TracesSampleRate < 0 || policy.TracesSampleRate > 1 {
		policy.TracesSampleRate = 0
	}
	if !policy.Enabled {
		policy = Policy{}
	}

	policyMu.Lock()
	defer policyMu.Unlock()
	if configured && policy == currentPolicy {
		return nil
	}
	if configured {
		sentry.Flush(flushTimeout)
	}
	if !policy.Enabled {
		sentry.CurrentHub().BindClient(nil)
		currentPolicy = Policy{}
		configured = true
		return nil
	}
	err := sentry.Init(sentry.ClientOptions{
		Dsn:              policy.BackendDSN,
		Environment:      policy.Environment,
		Release:          policy.Release,
		ServerName:       "hfl-platform-gateway",
		EnableTracing:    policy.TracesSampleRate > 0,
		TracesSampleRate: policy.TracesSampleRate,
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
		return err
	}
	currentPolicy = policy
	configured = true
	return nil
}

// Initialize enables Sentry for an explicitly configured Platform Gateway Agent.
// It returns a shutdown function that flushes pending events without blocking exit.
func Initialize() func() {
	policy := Policy{
		Enabled:          enabled(),
		BackendDSN:       strings.TrimSpace(os.Getenv("SENTRY_BACKEND_DSN")),
		Environment:      strings.TrimSpace(os.Getenv("SENTRY_ENVIRONMENT")),
		Release:          strings.TrimSpace(os.Getenv("SENTRY_RELEASE")),
		TracesSampleRate: sampleRate(),
	}
	if policy.Enabled && policy.BackendDSN == "" {
		_, _ = fmt.Fprintln(os.Stderr, "[sentry] backend DSN is missing; Agent reporting is disabled")
	}
	if err := Configure(policy); err != nil {
		_, _ = fmt.Fprintf(os.Stderr, "[sentry] Agent initialization failed; continuing: %v\n", err)
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
