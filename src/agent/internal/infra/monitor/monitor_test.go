package monitor

import (
	"context"
	"testing"
)

func TestSampleOnceReturnsPayload(t *testing.T) {
	sample, err := NewCollector().SampleOnce(context.Background())
	if err != nil {
		t.Fatalf("SampleOnce: %v", err)
	}
	payload := sample.ToPayload()
	if payload["cpu"] == nil {
		t.Fatal("expected cpu payload")
	}
	if payload["memory"] == nil {
		t.Fatal("expected memory payload")
	}
	if _, ok := payload["cpu_usage"]; !ok {
		t.Fatal("expected cpu_usage scalar")
	}
}
