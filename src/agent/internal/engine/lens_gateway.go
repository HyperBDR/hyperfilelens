package engine

import (
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

const lensWorkspaceTrashDirectory = ".hyperfilelens-trash"

func isLensReservedWorkspacePath(path, allowedRoot string) bool {
	_, relative, err := secureRelativePath(path, allowedRoot, true)
	if err != nil || relative == "." {
		return false
	}
	return strings.Split(relative, string(os.PathSeparator))[0] == lensWorkspaceTrashDirectory
}

func (e *Engine) runLensWorkspaceValidateLocal(ctx context.Context, p Payload) (string, map[string]any, string) {
	if err := ctx.Err(); err != nil {
		return "failed", nil, "canceled"
	}
	allowedRoot := payloadStringValue(p.Extra["allowed_root"])
	if isLensReservedWorkspacePath(p.Path, allowedRoot) {
		return "failed", nil, "path is reserved for managed workspace cleanup"
	}
	fd, cleanPath, err := secureOpenDirectory(p.Path, allowedRoot, true, uint64(os.O_RDONLY))
	if err != nil {
		return "failed", nil, err.Error()
	}
	file := secureDirectoryFile(fd, cleanPath)
	if file == nil {
		return "failed", nil, "restricted Data Gateway filesystem operations require Linux"
	}
	_ = file.Close()
	return "success", map[string]any{"path": cleanPath, "allowed_root": allowedRoot}, ""
}

func (e *Engine) runLensGatewayBrowse(ctx context.Context, p Payload) (string, map[string]any, string) {
	if err := ctx.Err(); err != nil {
		return "failed", nil, "canceled"
	}
	allowedRoot := payloadStringValue(p.Extra["allowed_root"])
	if isLensReservedWorkspacePath(p.Path, allowedRoot) {
		return "failed", nil, "path is reserved for managed workspace cleanup"
	}
	fd, cleanPath, err := secureOpenDirectory(p.Path, allowedRoot, true, uint64(os.O_RDONLY))
	if err != nil {
		return "failed", nil, err.Error()
	}
	directory := secureDirectoryFile(fd, cleanPath)
	if directory == nil {
		return "failed", nil, "restricted Data Gateway filesystem operations require Linux"
	}
	defer directory.Close()

	offset, _ := strconv.Atoi(p.Cursor)
	if offset < 0 {
		offset = 0
	}
	rows := make([]map[string]any, 0)
	matched := 0
	hasMore := false
	for {
		entries, readErr := directory.ReadDir(128)
		if readErr != nil && !errors.Is(readErr, io.EOF) {
			return "failed", nil, readErr.Error()
		}
		for _, entry := range entries {
			if cleanPath == filepath.Clean(allowedRoot) && entry.Name() == lensWorkspaceTrashDirectory {
				continue
			}
			if !entry.IsDir() || entry.Type()&os.ModeSymlink != 0 {
				continue
			}
			if matched < offset {
				matched++
				continue
			}
			rows = append(rows, map[string]any{
				"name":   entry.Name(),
				"path":   filepath.Join(cleanPath, entry.Name()),
				"is_dir": true,
			})
			matched++
			if p.Limit > 0 && len(rows) >= p.Limit {
				hasMore = true
				break
			}
		}
		if hasMore || errors.Is(readErr, io.EOF) {
			break
		}
	}
	nextCursor := ""
	if hasMore {
		nextCursor = strconv.Itoa(matched)
	}
	return "success", map[string]any{
		"path":        cleanPath,
		"entries":     rows,
		"count":       len(rows),
		"has_more":    hasMore,
		"next_cursor": nextCursor,
	}, ""
}
