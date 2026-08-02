package observability

import (
	"testing"

	"github.com/getsentry/sentry-go"
)

func TestSampleRateRejectsInvalidValues(t *testing.T) {
	t.Setenv("SENTRY_TRACES_SAMPLE_RATE", "2")
	if got := sampleRate(); got != 0 {
		t.Fatalf("sampleRate() = %v, want 0", got)
	}
}

func TestEnabledDefaultsToFalse(t *testing.T) {
	t.Setenv("SENTRY_ENABLED", "")
	if enabled() {
		t.Fatal("enabled() = true, want false")
	}
}

func TestEnabledRequiresServerManagedGatewayPolicy(t *testing.T) {
	t.Setenv("SENTRY_ENABLED", "true")
	t.Setenv("HFL_SENTRY_POLICY_MANAGED", "true")
	t.Setenv("HFL_NODE_ROLE", "agent")
	if enabled() {
		t.Fatal("ordinary Agent must not initialize Sentry")
	}

	t.Setenv("HFL_NODE_ROLE", "gateway")
	if !enabled() {
		t.Fatal("server-managed Gateway policy should initialize Sentry")
	}

	t.Setenv("HFL_SENTRY_POLICY_MANAGED", "")
	if enabled() {
		t.Fatal("unverified Gateway environment must not initialize Sentry")
	}
}

func TestConfigureEnablesAndDisablesRuntimeClient(t *testing.T) {
	resetRuntimePolicy := func() {
		policyMu.Lock()
		defer policyMu.Unlock()
		sentry.CurrentHub().BindClient(nil)
		currentPolicy = Policy{}
		configured = false
	}
	resetRuntimePolicy()
	t.Cleanup(resetRuntimePolicy)

	err := Configure(Policy{
		Enabled:          true,
		BackendDSN:       "https://public@sentry.example.com/25",
		Environment:      "hfl-test",
		Release:          "hyperfilelens-agent@main-123abcd",
		TracesSampleRate: 0,
	})
	if err != nil {
		t.Fatal(err)
	}
	client := sentry.CurrentHub().Client()
	if client == nil {
		t.Fatal("Configure() did not bind a Sentry client")
	}
	if client.Options().SendDefaultPII {
		t.Fatal("Configure() enabled default PII collection")
	}

	if err := Configure(Policy{}); err != nil {
		t.Fatal(err)
	}
	if sentry.CurrentHub().Client() != nil {
		t.Fatal("disabled policy did not unbind the Sentry client")
	}
}
