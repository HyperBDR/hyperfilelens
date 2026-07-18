package engine

import (
	"context"
	"testing"
)

func TestNormalizeRepositoryOperationKind(t *testing.T) {
	if got := NormalizeKind("repository.operation"); got != "repository.operation" {
		t.Fatalf("NormalizeKind() = %q", got)
	}
	if got := NormalizeKind("maintenance.gc"); got != "maintenance.gc" {
		t.Fatalf("legacy maintenance alias = %q", got)
	}
}

func TestRepositoryCleanupOperationTypesRouteToCleanupExecutor(t *testing.T) {
	for _, operationType := range []string{"cleanup.target", "cleanup.repository"} {
		status, _, errMsg := (&Engine{}).runManagedRepositoryOperation(
			context.Background(),
			ReporterSink{},
			"cleanup-task",
			Payload{Extra: map[string]any{"operation_type": operationType}},
		)
		if status != "failed" || errMsg != "repository payload is required" {
			t.Fatalf("operation %q routed incorrectly: status=%q error=%q", operationType, status, errMsg)
		}
	}
}

func TestNormalizeRepositoryInitializeKind(t *testing.T) {
	for _, kind := range []string{"repo.initialize", "repository.initialize"} {
		if got := NormalizeKind(kind); got != "repo.initialize" {
			t.Fatalf("NormalizeKind(%q) = %q", kind, got)
		}
	}
}
