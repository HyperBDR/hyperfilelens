//go:build windows

package enroll

import (
	"context"
	"fmt"
)

// InstallLensSidecar is not supported on Windows.
func InstallLensSidecar(ctx context.Context, cfg Config, lens LensSidecarConfig) error {
	return fmt.Errorf("AI engine install is Linux-only")
}

func ensureGatewayDocker(ctx context.Context, cfg Config) error {
	return fmt.Errorf("gateway-install requires Linux")
}

func lensSidecarHealthy() bool {
	return false
}
