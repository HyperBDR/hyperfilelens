//go:build !windows

package explorer

func extraMountPoints(seen map[string]struct{}) []string {
	_ = seen
	return nil
}
