//go:build linux

package engine

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/sys/unix"
)

const secureResolveFlags = unix.RESOLVE_BENEATH | unix.RESOLVE_NO_SYMLINKS

func secureOpenatBeneath(dirFD int, relative string, flags uint64) (int, error) {
	fd, err := unix.Openat2(dirFD, relative, &unix.OpenHow{
		Flags:   flags,
		Resolve: secureResolveFlags,
	})
	if err == nil || (!errors.Is(err, unix.ENOSYS) && !errors.Is(err, unix.EINVAL)) {
		return fd, err
	}
	// Ubuntu 20.04 may use a pre-openat2 5.4 kernel. Preserve the same
	// no-symlink, component-by-component boundary with directory FDs.
	components := strings.Split(relative, "/")
	currentFD := dirFD
	ownedCurrent := false
	for index, component := range components {
		if component == "" || component == "." {
			component = "."
		}
		componentFlags := uint64(unix.O_PATH | unix.O_DIRECTORY | unix.O_CLOEXEC | unix.O_NOFOLLOW)
		if index == len(components)-1 {
			componentFlags = flags
		}
		nextFD, openErr := unix.Openat(currentFD, component, int(componentFlags), 0)
		if ownedCurrent {
			_ = unix.Close(currentFD)
		}
		if openErr != nil {
			return -1, openErr
		}
		currentFD = nextFD
		ownedCurrent = true
	}
	return currentFD, nil
}

func validateLinuxAbsolutePath(path, field string) (string, error) {
	path = strings.TrimSpace(path)
	if path == "" {
		return "", fmt.Errorf("%s is required", field)
	}
	if strings.ContainsRune(path, '\x00') || strings.Contains(path, `\`) || !filepath.IsAbs(path) {
		return "", fmt.Errorf("%s must be an absolute Linux path", field)
	}
	for _, component := range strings.Split(path, "/") {
		if component == "." || component == ".." {
			return "", fmt.Errorf("%s contains an unsafe path component", field)
		}
	}
	return filepath.Clean(path), nil
}

func secureRelativePath(path, allowedRoot string, allowRoot bool) (string, string, error) {
	cleanRoot, err := validateLinuxAbsolutePath(allowedRoot, "allowed_root")
	if err != nil {
		return "", "", err
	}
	cleanPath, err := validateLinuxAbsolutePath(path, "path")
	if err != nil {
		return "", "", err
	}
	relative, err := filepath.Rel(cleanRoot, cleanPath)
	if err != nil || filepath.IsAbs(relative) || relative == ".." || strings.HasPrefix(relative, "../") {
		return "", "", errors.New("path must be contained by allowed_root")
	}
	if relative == "." && !allowRoot {
		return "", "", errors.New("path must be a child of allowed_root")
	}
	return cleanRoot, relative, nil
}

func secureOpenAbsoluteDirectory(path string) (int, error) {
	cleanPath, err := validateLinuxAbsolutePath(path, "path")
	if err != nil {
		return -1, err
	}
	rootFD, err := unix.Open("/", unix.O_PATH|unix.O_DIRECTORY|unix.O_CLOEXEC, 0)
	if err != nil {
		return -1, err
	}
	defer unix.Close(rootFD)
	relative := strings.TrimPrefix(cleanPath, "/")
	if relative == "" {
		relative = "."
	}
	return secureOpenatBeneath(
		rootFD,
		relative,
		unix.O_PATH|unix.O_DIRECTORY|unix.O_CLOEXEC|unix.O_NOFOLLOW,
	)
}

func secureOpenDirectory(path, allowedRoot string, allowRoot bool, flags uint64) (int, string, error) {
	cleanRoot, relative, err := secureRelativePath(path, allowedRoot, allowRoot)
	if err != nil {
		return -1, "", err
	}
	rootFD, err := secureOpenAbsoluteDirectory(cleanRoot)
	if err != nil {
		return -1, "", fmt.Errorf("allowed_root is not a safe directory: %w", err)
	}
	defer unix.Close(rootFD)
	if relative == "." {
		relative = "."
	}
	fd, err := secureOpenatBeneath(
		rootFD,
		relative,
		flags|unix.O_DIRECTORY|unix.O_CLOEXEC|unix.O_NOFOLLOW,
	)
	if err != nil {
		return -1, "", err
	}
	cleanPath := cleanRoot
	if relative != "." {
		cleanPath = filepath.Join(cleanRoot, relative)
	}
	return fd, cleanPath, nil
}

func secureEnsureDirectory(path, allowedRoot string, mode uint32) (string, bool, error) {
	cleanRoot, relative, err := secureRelativePath(path, allowedRoot, false)
	if err != nil {
		return "", false, err
	}
	rootFD, err := secureOpenAbsoluteDirectory(cleanRoot)
	if err != nil {
		return "", false, fmt.Errorf("allowed_root is not a safe directory: %w", err)
	}
	defer unix.Close(rootFD)

	currentFD, err := unix.Dup(rootFD)
	if err != nil {
		return "", false, err
	}
	defer func() { _ = unix.Close(currentFD) }()
	created := false
	for _, component := range strings.Split(relative, "/") {
		nextFD, openErr := secureOpenatBeneath(
			currentFD,
			component,
			unix.O_PATH|unix.O_DIRECTORY|unix.O_CLOEXEC|unix.O_NOFOLLOW,
		)
		if errors.Is(openErr, unix.ENOENT) {
			if mkdirErr := unix.Mkdirat(currentFD, component, mode); mkdirErr != nil && !errors.Is(mkdirErr, unix.EEXIST) {
				return "", false, mkdirErr
			}
			created = true
			nextFD, openErr = secureOpenatBeneath(
				currentFD,
				component,
				unix.O_PATH|unix.O_DIRECTORY|unix.O_CLOEXEC|unix.O_NOFOLLOW,
			)
		}
		if openErr != nil {
			return "", false, openErr
		}
		_ = unix.Close(currentFD)
		currentFD = nextFD
	}
	return filepath.Join(cleanRoot, relative), created, nil
}

func secureDirectoryFile(fd int, name string) *os.File {
	return os.NewFile(uintptr(fd), name)
}
