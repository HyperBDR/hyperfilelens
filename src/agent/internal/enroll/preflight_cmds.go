package enroll

import (
	"fmt"
	"os/exec"
	"runtime"
	"strings"
)

func checkRequiredCommands() error {
	missing := missingRequiredCommands()
	if len(missing) == 0 {
		return nil
	}
	return fmt.Errorf("%s", strings.Join(missing, ", "))
}

func missingRequiredCommands() []string {
	var missing []string
	for _, cmd := range requiredCommands() {
		if _, err := exec.LookPath(cmd); err != nil {
			missing = append(missing, cmd)
		}
	}
	return missing
}

func requiredCommands() []string {
	return requiredCommandsFor(runtime.GOOS)
}

func requiredCommandsFor(goos string) []string {
	switch goos {
	case "windows":
		// Enrollment and release downloads use the Go HTTP client. The Windows
		// bootstrap can also fall back to PowerShell when curl.exe is absent.
		return nil
	default:
		return []string{"bash", "curl", "tar"}
	}
}

func requiredCommandsDetail() string {
	return strings.Join(requiredCommands(), ", ")
}
