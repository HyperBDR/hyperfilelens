package enroll

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"runtime"

	"hyperfilelens/agent/internal/platform/install"
	"hyperfilelens/agent/internal/platform/release"
	"hyperfilelens/agent/internal/remote"
)

// RunInstall performs the full console enrollment pipeline.
func RunInstall(ctx context.Context, opts InstallOptions) error {
	cfg, err := LoadConfigFromEnv()
	if err != nil {
		logFail(err.Error(), 2)
	}

	envReport, err := RunEnvironmentChecks(ctx, cfg)
	if err != nil {
		logFail(err.Error(), 1)
	}

	state := envReport.Existing
	agentVer := state.Version

	if !state.Installed {
		if err := installAgentPackage(ctx, cfg, &agentVer); err != nil {
			logFail(err.Error(), 3)
		}
		return finishEnrollment(ctx, cfg, agentVer)
	}

	plan, err := PlanReinstall(ctx, cfg, state)
	if err != nil {
		logFail(err.Error(), 3)
	}

	switch plan.Action {
	case ActionCrossOrg:
		logFail(fmt.Sprintf(
			"This agent belongs to organization %q, but this enrollment link is for %q. Uninstall the agent first, then try again.",
			state.OrgKey, cfg.OrgKey,
		), 1)
	case ActionAlreadyEnrolled:
		if ver, verErr := InstalledAgentVersion(ctx); verErr == nil && ver != "" {
			agentVer = ver
		}
		info := summaryFromState(cfg.APIBase, state.NodeID, agentVer, state.Service)
		printAlreadyEnrolled(info)
		return nil
	}

	if plan.NeedsConfirm {
		if err := confirmAction(plan.ConfirmMessage, opts.AutoYes); err != nil {
			logFail(err.Error(), 1)
		}
	}

	switch plan.Action {
	case ActionRepair:
		if err := refreshAgentConfig(cfg); err != nil {
			logFail(err.Error(), 3)
		}
		if ver, verErr := InstalledAgentVersion(ctx); verErr == nil && ver != "" {
			agentVer = ver
		}
		return finishEnrollment(ctx, cfg, agentVer)

	case ActionUpgrade:
		if err := refreshAgentConfig(cfg); err != nil {
			logFail(err.Error(), 3)
		}
		dl := plan.DownloadURL
		releaseVer := plan.ReleaseVersion
		if dl == "" {
			var fetchErr error
			dl, releaseVer, fetchErr = release.FetchDownloadURLWithRetry(ctx, cfg.AgentConfig(), func(attempt, max int, retryErr error) {
				logWarn(fmt.Sprintf("Console release API unavailable (attempt %d/%d): %v", attempt, max, retryErr))
			})
			if fetchErr != nil {
				logFail("Failed to resolve the agent release: "+fetchErr.Error(), 3)
			}
		}
		if err := upgradeAgentPackage(ctx, cfg, dl, releaseVer); err != nil {
			logFail(err.Error(), 3)
		}
		if ver, verErr := InstalledAgentVersion(ctx); verErr == nil && ver != "" {
			agentVer = ver
		} else if releaseVer != "" {
			agentVer = releaseVer
		}
		return finishEnrollment(ctx, cfg, agentVer)

	case ActionRebind:
		if err := refreshAgentConfig(cfg); err != nil {
			logFail(err.Error(), 3)
		}
		if ver, verErr := InstalledAgentVersion(ctx); verErr == nil && ver != "" {
			agentVer = ver
		}
		return finishEnrollment(ctx, cfg, agentVer)
	}

	logFail("Unsupported reinstall action.", 3)
	return nil
}

func validateInstalledAgent(ctx context.Context) error {
	if _, err := InstalledAgentVersion(ctx); err != nil {
		return fmt.Errorf("installed agent verification failed: %w", err)
	}
	return nil
}

func refreshAgentConfig(cfg Config) error {
	logStep("Refreshing agent configuration.")
	if err := WriteEnrollmentEnv(cfg); err != nil {
		return err
	}
	logOK("Agent configuration was refreshed successfully.")
	return nil
}

func finishEnrollment(ctx context.Context, cfg Config, agentVer string) error {
	if err := validateInstalledAgent(ctx); err != nil {
		logFail(err.Error(), 3)
	}
	logOK("Agent binaries were verified successfully.")

	logStep("Registering node with the console.")
	agentCfg := cfg.AgentConfig()
	nodeID, err := remote.RegisterNodeHTTP(ctx, agentCfg, agentVer)
	if err != nil {
		if remote.IsInvalidEnrollmentToken(err) && agentCfg.NodeID != "" {
			nodeID = agentCfg.NodeID
			logOK(fmt.Sprintf("Using existing node %s because this enrollment link was already used.", nodeID))
		} else if remote.IsInvalidEnrollmentToken(err) {
			state := DetectInstallState()
			info := summaryFromState(cfg.APIBase, state.NodeID, state.Version, state.Service)
			printTokenAlreadyUsed(info)
			return nil
		} else {
			logFail("Node registration failed: "+err.Error(), 5)
		}
	} else {
		logOK(fmt.Sprintf("Node registered successfully (id=%s).", nodeID))
	}

	envPath := EnvFilePath()
	if err := WriteNodeID(envPath, nodeID); err != nil {
		logFail("Failed to update agent.env: "+err.Error(), 5)
	}

	logStep("Starting the agent service.")
	if err := StartInstalledService(ctx); err != nil {
		logFail("Agent service start failed: "+err.Error(), 6)
	}

	service := serviceState(ctx)
	if service == "" {
		service = "active"
	}
	logOK(fmt.Sprintf("Agent service is %s.", service))

	info := summaryFromState(cfg.APIBase, nodeID, agentVer, service)
	printEnrollmentSuccess(info)
	return nil
}

func installAgentPackage(ctx context.Context, cfg Config, agentVer *string) error {
	dl, releaseVersion, err := resolveRelease(ctx, cfg)
	if err != nil {
		return err
	}
	if releaseVersion != "" {
		*agentVer = releaseVersion
		logStep(fmt.Sprintf("Downloading agent version %s.", releaseVersion))
	} else {
		logStep("Downloading the agent package.")
	}

	archivePath, cleanup, err := downloadReleaseArchive(ctx, dl)
	if err != nil {
		return err
	}
	defer cleanup()

	bundleRoot, err := extractReleaseBundle(ctx, archivePath)
	if err != nil {
		return err
	}
	if err := validateAgentPackage(bundleRoot, cfg.NodeRole, releaseVersion); err != nil {
		return fmt.Errorf("Agent package validation failed: %w", err)
	}

	logStep("Installing agent binaries and service.")
	if err := RunBundleInstall(ctx, bundleRoot, cfg); err != nil {
		return err
	}
	logOK("Agent binaries and service were installed successfully.")

	if ver, verErr := InstalledAgentVersion(ctx); verErr == nil && ver != "" {
		*agentVer = ver
	}
	return nil
}

func upgradeAgentPackage(ctx context.Context, cfg Config, downloadURL, releaseVersion string) error {
	if releaseVersion != "" {
		logStep(fmt.Sprintf("Downloading agent version %s.", releaseVersion))
	} else {
		logStep("Downloading the agent package.")
	}

	archivePath, cleanup, err := downloadReleaseArchive(ctx, downloadURL)
	if err != nil {
		return err
	}
	defer cleanup()
	bundleRoot, err := extractReleaseBundle(ctx, archivePath)
	if err != nil {
		return err
	}
	if err := validateAgentPackage(bundleRoot, cfg.NodeRole, releaseVersion); err != nil {
		return fmt.Errorf("Agent package validation failed: %w", err)
	}

	logStep("Upgrading agent binaries.")
	if err := RunBundleUpgrade(ctx, archivePath); err != nil {
		return err
	}
	logOK("Agent binaries were upgraded successfully.")
	return nil
}

func resolveRelease(ctx context.Context, cfg Config) (downloadURL, version string, err error) {
	downloadURL, version, err = release.FetchDownloadURLWithRetry(ctx, cfg.AgentConfig(), func(attempt, max int, retryErr error) {
		logWarn(fmt.Sprintf("Console release API unavailable (attempt %d/%d): %v", attempt, max, retryErr))
	})
	if err != nil {
		return "", "", fmt.Errorf("Failed to resolve the agent release: %w", err)
	}
	return downloadURL, version, nil
}

func downloadReleaseArchive(ctx context.Context, downloadURL string) (archivePath string, cleanup func(), err error) {
	workDir, err := os.MkdirTemp("", "hfl-enroll-")
	if err != nil {
		return "", nil, fmt.Errorf("temp dir: %w", err)
	}
	cleanup = func() { _ = os.RemoveAll(workDir) }

	ext := ".tar.gz"
	if runtime.GOOS == "windows" {
		ext = ".zip"
	}
	archivePath = filepath.Join(workDir, "package"+ext)
	if err := install.DownloadURL(ctx, downloadURL, archivePath); err != nil {
		cleanup()
		return "", nil, fmt.Errorf("Download failed: %w", err)
	}
	return archivePath, cleanup, nil
}

func extractReleaseBundle(ctx context.Context, archivePath string) (string, error) {
	workDir := filepath.Dir(archivePath)
	extractDir := filepath.Join(workDir, "extract")
	if err := install.ExtractArchive(ctx, archivePath, extractDir); err != nil {
		return "", fmt.Errorf("Extract failed: %w", err)
	}
	bundleRoot, err := install.FindBundleRoot(extractDir)
	if err != nil {
		return "", fmt.Errorf("Invalid distribution archive: %w", err)
	}
	return bundleRoot, nil
}

func runtimeArch() string {
	if runtime.GOARCH == "arm64" {
		return "arm64"
	}
	return "amd64"
}
