//go:build windows

package enroll

import "os"

func readOnlyWritableAccess(path string) (bool, error) {
	info, err := os.Stat(path)
	if err != nil {
		return false, err
	}
	if !info.IsDir() {
		return false, os.ErrInvalid
	}
	// Windows ACL write checks require opening a file for write, which would
	// violate the preflight read-only guarantee. Defer the definitive check.
	return false, nil
}
