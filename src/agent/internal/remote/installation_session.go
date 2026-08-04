package remote

import (
	"context"

	"hyperfilelens/agent/internal/enrollmentclient"
	"hyperfilelens/agent/internal/model"
)

// InstallationSession is the server-authoritative authorization for one install.
type InstallationSession = enrollmentclient.InstallationSession

// OpenInstallationSession exchanges an enrollment token for a resumable session.
func OpenInstallationSession(
	ctx context.Context,
	cfg *model.AgentConfig,
	installationID string,
) (InstallationSession, error) {
	return enrollmentclient.OpenInstallationSession(ctx, cfg, installationID)
}

// ReleaseInstallationSession releases an unfinished installation session.
func ReleaseInstallationSession(
	ctx context.Context,
	cfg *model.AgentConfig,
	installationID string,
) error {
	return enrollmentclient.ReleaseInstallationSession(ctx, cfg, installationID)
}
