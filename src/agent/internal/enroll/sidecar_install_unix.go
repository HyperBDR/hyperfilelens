//go:build !windows

package enroll

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"hyperfilelens/agent/internal/platform/install"
)

const (
	lensEnvFilePath            = "/etc/hyperfilelens/lensnode.env"
	lensSidecarScript          = "gateway-install-lensnode-sidecar.sh"
	lensnodeImageArchive       = "lensnode-image-linux-amd64.tar.gz"
	gatewayDockerInstallScript = "gateway-install-docker-ubuntu-amd64.sh"
	defaultLensnodeImage       = "hyperfilelens-sourcelens-lensnode:latest"
	gatewayMinDockerEngine     = "24.0.0"
	gatewayMinDockerCompose    = "2.20.0"
)

// InstallLensSidecar writes LensNode credentials and runs the bundled sidecar install script.
func InstallLensSidecar(ctx context.Context, cfg Config, lens LensSidecarConfig) error {
	if err := writeLensEnvFile(lens); err != nil {
		return err
	}

	if lensSidecarHealthy() && os.Getenv("HFL_FORCE_SIDECAR_INSTALL") != "1" {
		logStep("LensNode sidecar is already running.")
		return nil
	}

	if err := ensureLensnodeImage(ctx, cfg); err != nil {
		return err
	}

	scriptPath, cleanup, err := downloadSidecarInstallScript(ctx, cfg)
	if err != nil {
		return err
	}
	defer cleanup()

	cmd := exec.CommandContext(ctx, "/bin/bash", scriptPath)
	cmd.Env = append(os.Environ(),
		"HFL_LENS_ENV_FILE="+lensEnvFilePath,
		"HFL_INSECURE_TLS="+insecureTLSEnv(),
		"LENSNODE_IMAGE="+defaultLensnodeImage,
	)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("sidecar install script: %w", err)
	}
	return nil
}

func ensureGatewayDocker(ctx context.Context, cfg Config) error {
	if dockerRuntimeReady() {
		logOK(fmt.Sprintf("Using existing Docker (engine %s).", dockerEngineVersion()))
		return nil
	}
	if _, err := exec.LookPath("docker"); err == nil {
		return fmt.Errorf("docker is installed but does not meet the requirements (engine >= %s, Compose v2 >= %s, reachable daemon); HFL will not repair or replace it", gatewayMinDockerEngine, gatewayMinDockerCompose)
	}
	scriptPath, cleanup, err := downloadGatewayBootstrapScript(ctx, cfg, gatewayDockerInstallScript)
	if err != nil {
		return err
	}
	defer cleanup()

	cmd := exec.CommandContext(ctx, "/bin/bash", scriptPath)
	cmd.Env = append(os.Environ(),
		"HFL_API_BASE="+strings.TrimRight(strings.TrimSpace(cfg.APIBase), "/"),
		"HFL_GATEWAY_BOOTSTRAP_BASE="+strings.TrimRight(strings.TrimSpace(cfg.APIBase), "/")+"/media/gateway-bootstrap",
		"HFL_INSECURE_TLS="+insecureTLSEnv(),
		"HFL_DOCKER_MIN_ENGINE="+gatewayMinDockerEngine,
		"HFL_COMPOSE_MIN_VERSION="+gatewayMinDockerCompose,
	)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("docker install script: %w", err)
	}
	if !dockerRuntimeReady() {
		return fmt.Errorf("docker is not ready after install")
	}
	return nil
}

func dockerRuntimeReady() bool {
	if _, err := exec.LookPath("docker"); err != nil {
		return false
	}
	if err := exec.Command("docker", "info").Run(); err != nil {
		return false
	}
	engine := strings.TrimSpace(dockerEngineVersion())
	if engine == "" || !dockerVersionGE(engine, gatewayMinDockerEngine) {
		return false
	}
	compose := strings.TrimSpace(dockerComposeVersion())
	if compose == "" || !dockerVersionGE(compose, gatewayMinDockerCompose) {
		return false
	}
	return true
}

func dockerComposeVersion() string {
	out, err := exec.Command("docker", "compose", "version", "--short").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

func dockerEngineVersion() string {
	out, err := exec.Command("docker", "version", "--format", "{{.Server.Version}}").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

func dockerVersionGE(have, want string) bool {
	cmd := exec.Command("dpkg", "--compare-versions", have, "ge", want)
	return cmd.Run() == nil
}

func lensSidecarHealthy() bool {
	if _, err := exec.LookPath("docker"); err != nil {
		return false
	}
	cmd := exec.Command("docker", "ps",
		"--filter", "name=hyperfilelens-gateway",
		"--filter", "status=running",
		"--format", "{{.Names}}",
	)
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(out), "\n") {
		name := strings.TrimSpace(line)
		if name == "hyperfilelens-gateway-lensnode-1" || name == "hyperfilelens-gateway_lensnode_1" {
			return true
		}
	}
	return false
}

func writeLensEnvFile(lens LensSidecarConfig) error {
	dir := filepath.Dir(lensEnvFilePath)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("create %s: %w", dir, err)
	}

	lines := []string{
		"# HyperFileLens SourceLens LensNode sidecar (managed by hfl-enroll gateway-install)",
		"LENS_BASE_URL=" + quoteEnv(lens.LensBaseURL),
		"LENSNODE_TOKEN=" + quoteEnv(lens.LensnodeToken),
		"LENSNODE_UUID=" + quoteEnv(lens.LensnodeUUID),
		"HFL_WORKSPACE_ROOT=" + quoteEnv(lens.WorkspaceRoot),
	}
	if lens.LensnodeName != "" {
		lines = append(lines, "LENSNODE_NAME="+quoteEnv(lens.LensnodeName))
	}
	content := strings.Join(lines, "\n") + "\n"
	if err := os.WriteFile(lensEnvFilePath, []byte(content), 0o600); err != nil {
		return fmt.Errorf("write %s: %w", lensEnvFilePath, err)
	}
	return nil
}

func quoteEnv(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return `""`
	}
	if !strings.ContainsAny(value, " \t$\"'\\") {
		return value
	}
	return `"` + strings.ReplaceAll(value, `"`, `\"`) + `"`
}

func ensureLensnodeImage(ctx context.Context, cfg Config) error {
	if dockerImageExists(defaultLensnodeImage) && lensnodeImageSupportsInsecureTLS(defaultLensnodeImage) {
		return nil
	}
	if dockerImageExists(defaultLensnodeImage) {
		logWarn("Local LensNode image lacks HFL TLS bypass support; loading console bundle.")
	}

	workDir, err := os.MkdirTemp("", "hfl-lens-image-")
	if err != nil {
		return err
	}
	defer func() { _ = os.RemoveAll(workDir) }()

	url := strings.TrimRight(cfg.APIBase, "/") + "/media/gateway-bootstrap/" + lensnodeImageArchive
	archivePath := filepath.Join(workDir, lensnodeImageArchive)
	logStep("Downloading LensNode container image bundle.")
	if err := install.DownloadURL(ctx, url, archivePath); err != nil {
		return fmt.Errorf("download lensnode image bundle: %w", err)
	}

	logStep("Loading LensNode container image.")
	cmd := exec.CommandContext(ctx, "docker", "load", "-i", archivePath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("docker load lensnode image: %w", err)
	}
	for _, ref := range []string{
		defaultLensnodeImage,
		"sourcelens-lensnode:latest",
		"oneprocloud/sourcelens-lensnode:latest",
	} {
		if dockerImageExists(ref) {
			if !lensnodeImageSupportsInsecureTLS(ref) {
				return fmt.Errorf("lensnode image %s is missing HFL TLS bypass support; rebuild SourceLens with HFL patches and republish gateway-bootstrap bundle", ref)
			}
			return nil
		}
	}
	return fmt.Errorf("lensnode image not present after docker load (expected %s)", defaultLensnodeImage)
}

func lensnodeImageSupportsInsecureTLS(ref string) bool {
	cmd := exec.Command(
		"docker", "run", "--rm",
		"-e", "LENSNODE_INSECURE_TLS=1",
		ref,
		"python", "-c", "from lensnode.tls import tls_insecure_enabled; raise SystemExit(0 if tls_insecure_enabled() else 1)",
	)
	return cmd.Run() == nil
}

func dockerImageExists(ref string) bool {
	cmd := exec.Command("docker", "image", "inspect", ref)
	return cmd.Run() == nil
}

func downloadSidecarInstallScript(ctx context.Context, cfg Config) (scriptPath string, cleanup func(), err error) {
	return downloadGatewayBootstrapScript(ctx, cfg, lensSidecarScript)
}

func downloadGatewayBootstrapScript(ctx context.Context, cfg Config, name string) (scriptPath string, cleanup func(), err error) {
	workDir, err := os.MkdirTemp("", "hfl-gw-bootstrap-")
	if err != nil {
		return "", nil, err
	}
	cleanup = func() { _ = os.RemoveAll(workDir) }

	url := strings.TrimRight(cfg.APIBase, "/") + "/media/gateway-bootstrap/" + name
	dest := filepath.Join(workDir, name)
	if err := install.DownloadURL(ctx, url, dest); err != nil {
		cleanup()
		return "", nil, fmt.Errorf("download %s: %w", name, err)
	}
	if err := os.Chmod(dest, 0o755); err != nil {
		cleanup()
		return "", nil, err
	}
	return dest, cleanup, nil
}

func insecureTLSEnv() string {
	if os.Getenv("HFL_INSECURE_TLS") == "0" {
		return "0"
	}
	return "1"
}
