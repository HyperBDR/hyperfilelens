package observability

import "testing"

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
