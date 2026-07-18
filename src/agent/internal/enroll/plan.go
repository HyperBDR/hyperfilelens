package enroll

import (
	"context"
	"fmt"
	"strings"

	"hyperfilelens/agent/internal/platform/release"
)

// ReinstallAction describes what to do when agent binaries already exist.
type ReinstallAction string

const (
	ActionFreshInstall     ReinstallAction = "fresh_install"
	ActionAlreadyEnrolled  ReinstallAction = "already_enrolled"
	ActionRepair           ReinstallAction = "repair"
	ActionUpgrade          ReinstallAction = "upgrade"
	ActionRebind           ReinstallAction = "rebind"
	ActionCrossOrg         ReinstallAction = "cross_org"
)

// ReinstallPlan is the resolved path for an enrollment run on an existing install.
type ReinstallPlan struct {
	Action         ReinstallAction
	NeedsConfirm   bool
	ConfirmMessage string
	ReleaseVersion string
	DownloadURL    string
}

// PlanReinstall decides how to handle enrollment when the agent is already installed.
func PlanReinstall(ctx context.Context, cfg Config, state InstallState) (ReinstallPlan, error) {
	if state.OrgKey != "" && !strings.EqualFold(state.OrgKey, cfg.OrgKey) {
		return ReinstallPlan{Action: ActionCrossOrg}, nil
	}

	healthy := state.ServiceHealthy()
	hasNode := strings.TrimSpace(state.NodeID) != ""

	dl, releaseVer, releaseErr := release.FetchDownloadURL(ctx, cfg.AgentConfig())
	_ = releaseErr

	if hasNode && healthy {
		if releaseVer != "" && state.Version != "" && versionGreater(releaseVer, state.Version) {
			return ReinstallPlan{
				Action:         ActionUpgrade,
				NeedsConfirm:   true,
				ReleaseVersion: releaseVer,
				DownloadURL:    dl,
				ConfirmMessage: fmt.Sprintf(
					"Version %s is installed, but the console offers version %s. Upgrade may briefly interrupt backups.",
					state.Version, releaseVer,
				),
			}, nil
		}
		return ReinstallPlan{Action: ActionAlreadyEnrolled}, nil
	}

	if hasNode && !healthy {
		if releaseVer != "" && state.Version != "" && versionGreater(releaseVer, state.Version) {
			return ReinstallPlan{
				Action:         ActionUpgrade,
				NeedsConfirm:   true,
				ReleaseVersion: releaseVer,
				DownloadURL:    dl,
				ConfirmMessage: fmt.Sprintf(
					"Node %s is enrolled, but the service is %s. Upgrade %s and restart the agent?",
					state.NodeID, state.Service, versionLabel(state.Version, releaseVer),
				),
			}, nil
		}
		return ReinstallPlan{
			Action:       ActionRepair,
			NeedsConfirm: true,
			ConfirmMessage: fmt.Sprintf(
				"Node %s is enrolled, but the service is %s. Restart the agent service and reconnect to the console?",
				state.NodeID, state.Service,
			),
		}, nil
	}

	return ReinstallPlan{
		Action:       ActionRebind,
		NeedsConfirm: true,
		ConfirmMessage: "The agent is installed but not registered with the console. Bind this host now?",
	}, nil
}
