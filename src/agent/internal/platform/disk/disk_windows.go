//go:build windows

package disk

import "golang.org/x/sys/windows"

// Usage returns total/used/free bytes for the filesystem containing path.
func Usage(path string) (total, used, free uint64, err error) {
	p, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return 0, 0, 0, err
	}
	var freeAvail, totalBytes, totalFree uint64
	if err := windows.GetDiskFreeSpaceEx(p, &freeAvail, &totalBytes, &totalFree); err != nil {
		return 0, 0, 0, err
	}
	used = totalBytes - totalFree
	return totalBytes, used, freeAvail, nil
}
