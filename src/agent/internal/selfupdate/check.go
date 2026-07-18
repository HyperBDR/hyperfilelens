package selfupdate

// Version is the agent semver or pre-release tag (overridden by -ldflags at link time).
var Version = "0.1.0"

// Commit is the VCS revision embedded at build time.
var Commit = "unknown"

// NeedsUpdate reports whether remoteVersion is newer than the running build.
func NeedsUpdate(remoteVersion string) bool {
	return remoteVersion != "" && remoteVersion != Version
}
