package engine

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/google/uuid"
)

const lensWorkspaceIdentityKind = "managed_restore"

var removeLensWorkspaceTrash = os.RemoveAll

type lensWorkspaceIdentity struct {
	Version              int    `json:"version"`
	WorkspaceUID         string `json:"workspace_uid"`
	TenantOrganizationID string `json:"tenant_organization_id"`
	GatewayLinkID        string `json:"gateway_link_id"`
	KnowledgeSourceID    string `json:"knowledge_source_id"`
	WorkspaceKind        string `json:"workspace_kind"`
}

type lensWorkspacePaths struct {
	Root         string
	Workspace    string
	MetadataRoot string
	IdentityRoot string
	Identity     string
	TrashRoot    string
	Trash        string
}

func lensWorkspaceIdentityFromPayload(p Payload) (lensWorkspaceIdentity, error) {
	identity := lensWorkspaceIdentity{
		Version:              1,
		WorkspaceUID:         payloadStringValue(p.Extra["workspace_uid"]),
		TenantOrganizationID: payloadStringValue(p.Extra["tenant_organization_id"]),
		GatewayLinkID:        payloadStringValue(p.Extra["gateway_link_id"]),
		KnowledgeSourceID:    payloadStringValue(p.Extra["knowledge_source_id"]),
		WorkspaceKind:        payloadStringValue(p.Extra["workspace_kind"]),
	}
	if identity.WorkspaceUID == "" || identity.TenantOrganizationID == "" ||
		identity.GatewayLinkID == "" || identity.KnowledgeSourceID == "" {
		return lensWorkspaceIdentity{}, errors.New("managed workspace identity is incomplete")
	}
	if identity.WorkspaceKind != lensWorkspaceIdentityKind {
		return lensWorkspaceIdentity{}, errors.New("unsupported managed workspace kind")
	}
	workspaceUID, err := uuid.Parse(identity.WorkspaceUID)
	if err != nil || workspaceUID.String() != strings.ToLower(identity.WorkspaceUID) {
		return lensWorkspaceIdentity{}, errors.New("managed workspace UID is invalid")
	}
	identity.WorkspaceUID = workspaceUID.String()
	return identity, nil
}

func resolveLensWorkspacePaths(path, workspaceRoot, workspaceUID string) (lensWorkspacePaths, error) {
	rawRoot := strings.TrimSpace(workspaceRoot)
	rawPath := strings.TrimSpace(path)
	for field, value := range map[string]string{"path": rawPath, "workspace_root": rawRoot} {
		if strings.ContainsRune(value, '\x00') || strings.Contains(value, `\`) {
			return lensWorkspacePaths{}, fmt.Errorf("%s contains an unsupported character", field)
		}
		for _, component := range strings.Split(value, "/") {
			if component == "." || component == ".." {
				return lensWorkspacePaths{}, fmt.Errorf("%s contains an unsafe path component", field)
			}
		}
	}
	cleanRoot := filepath.Clean(rawRoot)
	cleanPath := filepath.Clean(rawPath)
	if cleanRoot == "." || cleanPath == "." || !filepath.IsAbs(cleanRoot) || !filepath.IsAbs(cleanPath) {
		return lensWorkspacePaths{}, errors.New("path and workspace_root must be absolute")
	}
	relative, err := filepath.Rel(cleanRoot, cleanPath)
	if err != nil || relative == "." || filepath.IsAbs(relative) || relative == ".." || strings.HasPrefix(relative, ".."+string(os.PathSeparator)) {
		return lensWorkspacePaths{}, errors.New("path must be a child of workspace_root")
	}
	if strings.Split(relative, string(os.PathSeparator))[0] == lensWorkspaceTrashDirectory {
		return lensWorkspacePaths{}, errors.New("path is reserved for managed workspace cleanup")
	}
	metadataRoot := filepath.Join(filepath.Dir(cleanRoot), ".hyperfilelens")
	identityRoot := filepath.Join(metadataRoot, "identities")
	// Quarantine must stay below the workspace root so rename remains atomic
	// when the workspace root is a dedicated filesystem mount.
	trashRoot := filepath.Join(cleanRoot, lensWorkspaceTrashDirectory)
	return lensWorkspacePaths{
		Root:         cleanRoot,
		Workspace:    cleanPath,
		MetadataRoot: metadataRoot,
		IdentityRoot: identityRoot,
		Identity:     filepath.Join(identityRoot, workspaceUID+".json"),
		TrashRoot:    trashRoot,
		Trash:        filepath.Join(trashRoot, workspaceUID),
	}, nil
}

func ensureLensMetadataLayout(paths lensWorkspacePaths) error {
	base := filepath.Dir(paths.Root)
	for _, path := range []string{paths.MetadataRoot, paths.IdentityRoot, paths.TrashRoot} {
		if _, _, err := secureEnsureDirectory(path, base, 0o700); err != nil {
			return fmt.Errorf("create protected gateway metadata: %w", err)
		}
		if err := os.Chmod(path, 0o700); err != nil {
			return fmt.Errorf("protect gateway metadata: %w", err)
		}
	}
	return nil
}

func readLensWorkspaceIdentity(identityPath string) (lensWorkspaceIdentity, error) {
	info, err := os.Lstat(identityPath)
	if err != nil {
		return lensWorkspaceIdentity{}, err
	}
	if info.Mode()&os.ModeSymlink != 0 || !info.Mode().IsRegular() {
		return lensWorkspaceIdentity{}, errors.New("managed workspace identity is not a regular file")
	}
	identityBytes, err := os.ReadFile(identityPath)
	if err != nil {
		return lensWorkspaceIdentity{}, err
	}
	var identity lensWorkspaceIdentity
	if err := json.Unmarshal(identityBytes, &identity); err != nil {
		return lensWorkspaceIdentity{}, errors.New("managed workspace identity is invalid")
	}
	return identity, nil
}

func writeLensWorkspaceIdentity(identityPath string, identity lensWorkspaceIdentity) error {
	encoded, err := json.Marshal(identity)
	if err != nil {
		return err
	}
	file, err := os.OpenFile(identityPath, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		return err
	}
	complete := false
	defer func() {
		_ = file.Close()
		if !complete {
			_ = os.Remove(identityPath)
		}
	}()
	if _, err := file.Write(encoded); err != nil {
		return err
	}
	if err := file.Sync(); err != nil {
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	complete = true
	return nil
}

func validateLensWorkspaceIdentity(identityPath string, expected lensWorkspaceIdentity) error {
	existing, err := readLensWorkspaceIdentity(identityPath)
	if err != nil {
		return errors.New("managed workspace identity is missing or invalid")
	}
	if existing != expected {
		return errors.New("managed workspace identity does not match")
	}
	return nil
}

func validateLensManagedRestoreTarget(p Payload, targetPath string) error {
	managedPath := payloadStringValue(p.Extra["managed_workspace_path"])
	if managedPath == "" {
		return nil
	}
	identity, err := lensWorkspaceIdentityFromPayload(p)
	if err != nil {
		return err
	}
	paths, err := resolveLensWorkspacePaths(
		managedPath,
		payloadStringValue(p.Extra["workspace_root"]),
		identity.WorkspaceUID,
	)
	if err != nil {
		return err
	}
	fd, cleanWorkspace, err := secureOpenDirectory(paths.Workspace, paths.Root, false, uint64(os.O_RDONLY))
	if err != nil {
		return err
	}
	workspaceDirectory := secureDirectoryFile(fd, cleanWorkspace)
	if workspaceDirectory == nil {
		return errors.New("restricted Data Gateway filesystem operations require Linux")
	}
	_ = workspaceDirectory.Close()
	if err := validateLensWorkspaceIdentity(paths.Identity, identity); err != nil {
		return err
	}

	cleanTarget := filepath.Clean(strings.TrimSpace(targetPath))
	relativeTarget, err := filepath.Rel(paths.Workspace, cleanTarget)
	if err != nil || filepath.IsAbs(relativeTarget) || relativeTarget == ".." || strings.HasPrefix(relativeTarget, ".."+string(os.PathSeparator)) {
		return errors.New("restore target must be inside its managed workspace")
	}
	current := paths.Workspace
	for _, component := range strings.Split(relativeTarget, string(os.PathSeparator)) {
		if component == "." || component == "" {
			continue
		}
		current = filepath.Join(current, component)
		info, statErr := os.Lstat(current)
		if os.IsNotExist(statErr) {
			break
		}
		if statErr != nil {
			return statErr
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("managed restore target contains a symlink: %s", current)
		}
	}
	return nil
}

func (e *Engine) runLensKsPrepare(ctx context.Context, p Payload) (string, map[string]any, string) {
	if err := ctx.Err(); err != nil {
		return "failed", nil, "canceled"
	}
	identity, err := lensWorkspaceIdentityFromPayload(p)
	if err != nil {
		return "failed", nil, err.Error()
	}
	paths, err := resolveLensWorkspacePaths(p.Path, payloadStringValue(p.Extra["workspace_root"]), identity.WorkspaceUID)
	if err != nil {
		return "failed", nil, err.Error()
	}
	if err := ensureLensMetadataLayout(paths); err != nil {
		return "failed", nil, err.Error()
	}
	existing, err := readLensWorkspaceIdentity(paths.Identity)
	if err == nil {
		if existing != identity {
			return "failed", nil, "managed workspace identity does not match"
		}
		cleanPath, created, ensureErr := secureEnsureDirectory(
			paths.Workspace,
			paths.Root,
			0o755,
		)
		if ensureErr != nil {
			return "failed", nil, ensureErr.Error()
		}
		return "success", map[string]any{"path": cleanPath, "created": created}, ""
	}
	if !os.IsNotExist(err) {
		return "failed", nil, err.Error()
	}
	if _, statErr := os.Lstat(paths.Workspace); statErr == nil {
		return "failed", nil, "refusing to claim an existing workspace without identity"
	} else if !os.IsNotExist(statErr) {
		return "failed", nil, statErr.Error()
	}
	// The durable identity is the creation journal. If the process exits before
	// the directory is created, a retry can safely complete the matching claim.
	if err := writeLensWorkspaceIdentity(paths.Identity, identity); err != nil {
		if os.IsExist(err) {
			existing, readErr := readLensWorkspaceIdentity(paths.Identity)
			if readErr != nil || existing != identity {
				return "failed", nil, "managed workspace identity does not match"
			}
		} else {
			return "failed", nil, err.Error()
		}
	}
	cleanPath, created, err := secureEnsureDirectory(paths.Workspace, paths.Root, 0o755)
	if err != nil {
		// Keep the matching identity as a recovery journal for the next retry.
		return "failed", nil, err.Error()
	}
	return "success", map[string]any{"path": cleanPath, "created": created}, ""
}

func (e *Engine) runLensKsCleanup(ctx context.Context, p Payload) (string, map[string]any, string) {
	if err := ctx.Err(); err != nil {
		return "failed", nil, "canceled"
	}
	identity, err := lensWorkspaceIdentityFromPayload(p)
	if err != nil {
		return "failed", nil, err.Error()
	}
	paths, err := resolveLensWorkspacePaths(p.Path, payloadStringValue(p.Extra["workspace_root"]), identity.WorkspaceUID)
	if err != nil {
		return "failed", nil, err.Error()
	}
	workspaceMissing := pathMissing(paths.Workspace)
	trashMissing := pathMissing(paths.Trash)
	identityMissing := pathMissing(paths.Identity)
	if workspaceMissing && trashMissing && identityMissing {
		return "success", map[string]any{"path": paths.Workspace, "removed": false}, ""
	}
	if err := validateLensWorkspaceIdentity(paths.Identity, identity); err != nil {
		return "failed", nil, err.Error()
	}
	if err := ensureLensMetadataLayout(paths); err != nil {
		return "failed", nil, err.Error()
	}

	workspaceExists := !workspaceMissing
	trashExists := !trashMissing
	if workspaceExists && trashExists {
		return "failed", nil, "managed workspace and trash both exist"
	}
	if workspaceExists {
		fd, _, openErr := secureOpenDirectory(paths.Workspace, paths.Root, false, uint64(os.O_RDONLY))
		if openErr != nil {
			return "failed", nil, openErr.Error()
		}
		workspaceDirectory := secureDirectoryFile(fd, paths.Workspace)
		if workspaceDirectory == nil {
			return "failed", nil, "restricted Data Gateway filesystem operations require Linux"
		}
		_ = workspaceDirectory.Close()
		if err := os.Rename(paths.Workspace, paths.Trash); err != nil {
			return "failed", nil, err.Error()
		}
		trashExists = true
	}
	if trashExists {
		if err := removeLensWorkspaceTrash(paths.Trash); err != nil {
			// The external identity intentionally survives partial deletion so a
			// retry can safely finish removing the quarantined workspace.
			return "failed", nil, err.Error()
		}
	}
	if err := os.Remove(paths.Identity); err != nil && !os.IsNotExist(err) {
		return "failed", nil, err.Error()
	}
	return "success", map[string]any{"path": paths.Workspace, "removed": workspaceExists || trashExists}, ""
}

func pathMissing(path string) bool {
	_, err := os.Lstat(path)
	return os.IsNotExist(err)
}
