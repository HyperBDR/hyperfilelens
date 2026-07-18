//go:build !windows

package svcwrap

import "context"

// RunIfService is a no-op on non-Windows platforms.
func RunIfService(run func(context.Context) error) (handled bool, err error) {
	_ = run
	return false, nil
}
