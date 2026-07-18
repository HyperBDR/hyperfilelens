//go:build !windows

package enroll

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"hyperfilelens/agent/internal/model"
	"hyperfilelens/agent/internal/platform/vfs"
)

const gatewayLifecycleScript = "gateway-lifecycle.sh"

// RunGatewayUpgrade upgrades the HFL agent bundle (optional) and LensNode sidecar.
func RunGatewayUpgrade(ctx context.Context, fromArchive string) error {
	cfg, err := LoadConfigFromEnv()
	if err != nil {
		logFail(err.Error(), 2)
	}
	if cfg.NodeRole != model.RoleGateway {
		logFail("gateway-upgrade requires HFL_NODE_ROLE=gateway", 2)
	}
	if runtime.GOOS != "linux" {
		logFail("gateway-upgrade is Linux-only", 2)
	}

	fromArchive = strings.TrimSpace(fromArchive)
	if fromArchive != "" {
		installDir := vfs.DefaultInstallDir()
		installScript := filepath.Join(installDir, "install.sh")
		logStep("Upgrading HyperFileLens agent.")
		cmd := exec.CommandContext(ctx, "/bin/bash", installScript, "upgrade", "--from", fromArchive, "--yes", "--quiet-footer")
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("agent upgrade: %w", err)
		}
	}

	logStep("Upgrading AI engine (LensNode sidecar).")
	if err := runGatewayLifecycleScript(ctx, cfg, "upgrade-sidecar", false); err != nil {
		return err
	}
	logOK("Data Gateway upgrade completed.")
	return nil
}

// RunGatewayUninstall removes LensNode sidecar then the HFL agent (default purge-all).
func RunGatewayUninstall(ctx context.Context, purgeAll bool) error {
	cfg, err := LoadConfigFromEnv()
	if err != nil {
		logFail(err.Error(), 2)
	}
	if cfg.NodeRole != model.RoleGateway {
		logFail("gateway-uninstall requires HFL_NODE_ROLE=gateway", 2)
	}
	if runtime.GOOS != "linux" {
		logFail("gateway-uninstall is Linux-only", 2)
	}

	logStep("Removing AI engine (LensNode sidecar).")
	if err := runGatewayLifecycleScript(ctx, cfg, "uninstall-sidecar", purgeAll); err != nil {
		return err
	}

	installDir := vfs.DefaultInstallDir()
	installScript := filepath.Join(installDir, "install.sh")
	if _, err := os.Stat(installScript); err != nil {
		logOK("Agent install bundle not found; sidecar removal completed.")
		return nil
	}

	logStep("Removing HyperFileLens agent.")
	args := []string{installScript, "uninstall"}
	if purgeAll {
		args = append(args, "--purge-all")
	}
	cmd := exec.CommandContext(ctx, "/bin/bash", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("agent uninstall: %w", err)
	}
	logOK("Data Gateway uninstall completed.")
	return nil
}

func runGatewayLifecycleScript(ctx context.Context, cfg Config, command string, purgeAll bool) error {
	scriptPath, cleanup, err := downloadGatewayBootstrapScript(ctx, cfg, gatewayLifecycleScript)
	if err != nil {
		return err
	}
	defer cleanup()

	args := []string{scriptPath, command}
	if purgeAll {
		args = append(args, "--purge-all")
	}
	cmd := exec.CommandContext(ctx, "/bin/bash", args...)
	cmd.Env = append(os.Environ(),
		"HFL_AGENT_ENV_FILE="+EnvFilePath(),
		"HFL_INSECURE_TLS="+insecureTLSEnv(),
	)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("%s: %w", command, err)
	}
	return nil
}
