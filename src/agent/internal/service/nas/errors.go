package nas

import "fmt"

// SMBCharsetUnavailableError means the proxy kernel cannot provide the
// configured CIFS filename charset. Continuing without it can corrupt paths.
type SMBCharsetUnavailableError struct {
	Charset string
	Kernel  string
	Cause   string
}

func (e *SMBCharsetUnavailableError) Error() string {
	kernel := e.Kernel
	if kernel == "" {
		kernel = "the running kernel"
	}
	return fmt.Sprintf(
		"SMB filename charset %q is unavailable on this proxy (%s): %s. Install the kernel extra-modules package matching %s, then remount the share.",
		e.Charset,
		kernel,
		e.Cause,
		kernel,
	)
}
