package vfs

import "path/filepath"

// AgentBackupDir is DATA_DIR/backup (rollback + state snapshots).
func AgentBackupDir(dataRoot string) string {
	return filepath.Join(dataRoot, "backup")
}

// AgentRuntimeDir is DATA_DIR/runtime (download + workspace).
func AgentRuntimeDir(dataRoot string) string {
	return filepath.Join(dataRoot, "runtime")
}

// AgentLifecycleDir is DATA_DIR/lifecycle (detached upgrade/uninstall).
func AgentLifecycleDir(dataRoot string) string {
	return filepath.Join(dataRoot, "lifecycle")
}
