//go:build !linux

package engine

import (
	"errors"
	"os"
)

var errRestrictedGatewayUnsupported = errors.New("restricted Data Gateway filesystem operations require Linux")

func secureOpenDirectory(path, allowedRoot string, allowRoot bool, flags uint64) (int, string, error) {
	return -1, "", errRestrictedGatewayUnsupported
}

func secureEnsureDirectory(path, allowedRoot string, mode uint32) (string, bool, error) {
	return "", false, errRestrictedGatewayUnsupported
}

func secureDirectoryFile(fd int, name string) *os.File {
	return nil
}
