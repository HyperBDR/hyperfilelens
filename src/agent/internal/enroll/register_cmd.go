package enroll

import (
	"context"
	"fmt"
	"strings"

	"hyperfilelens/agent/internal/platform/install"
)

// RunRegister sends enrollment heartbeat and persists node_id (install must already exist).
func RunRegister(ctx context.Context, opts InstallOptions) error {
	cfg, err := LoadConfigFromEnv()
	if err != nil {
		logFail(err.Error(), 2)
	}
	envReport, err := RunEnvironmentChecks(ctx, cfg)
	if err != nil {
		logFail(err.Error(), 1)
	}

	state := envReport.Existing
	if !state.Installed {
		logFail("The agent is not installed. Run hfl-enroll install first.", 2)
	}

	if state.OrgKey != "" && !strings.EqualFold(state.OrgKey, cfg.OrgKey) {
		logFail("This agent belongs to a different organization. Uninstall it first, then try again.", 1)
	}

	if state.NodeID != "" && state.ServiceHealthy() {
		agentVer := state.Version
		if ver, verErr := InstalledAgentVersion(ctx); verErr == nil && ver != "" {
			agentVer = ver
		}
		info := summaryFromState(cfg.APIBase, state.NodeID, agentVer, state.Service)
		printAlreadyEnrolled(info)
		return nil
	}

	plan, err := PlanReinstall(ctx, cfg, state)
	if err != nil {
		logFail(err.Error(), 3)
	}
	if plan.Action == ActionAlreadyEnrolled {
		info := summaryFromState(cfg.APIBase, state.NodeID, state.Version, state.Service)
		printAlreadyEnrolled(info)
		return nil
	}
	if plan.NeedsConfirm {
		if err := confirmAction(plan.ConfirmMessage, opts.AutoYes); err != nil {
			logFail(err.Error(), 1)
		}
	}

	if err := refreshAgentConfig(cfg); err != nil {
		logFail(err.Error(), 3)
	}

	agentVer, verErr := InstalledAgentVersion(ctx)
	if verErr != nil {
		logWarn(verErr.Error())
	}

	return finishEnrollment(ctx, cfg, agentVer)
}

// RunStatus prints installed agent enrollment status.
func RunStatus(ctx context.Context) error {
	envPath := EnvFilePath()
	state := DetectInstallState()
	installDir := install.DefaultInstallDir()

	logInfo("HyperFileLens agent status report.")
	if state.Installed {
		if state.Version != "" {
			logOK(fmt.Sprintf("Agent is installed (version %s).", state.Version))
		} else {
			logOK("Agent is installed.")
		}
	} else {
		logInfo("Agent is not installed.")
	}
	if state.NodeID != "" {
		logInfo(fmt.Sprintf("Node id: %s.", state.NodeID))
	} else {
		logInfo("Node id: not registered.")
	}
	if state.Service != "" {
		logInfo(fmt.Sprintf("Service: %s.", state.Service))
	}
	if state.OrgKey != "" {
		logInfo(fmt.Sprintf("Organization: %s.", state.OrgKey))
	}
	logInfo(fmt.Sprintf("Config: %s.", envPath))
	logInfo(fmt.Sprintf("Install directory: %s.", installDir))
	return nil
}
