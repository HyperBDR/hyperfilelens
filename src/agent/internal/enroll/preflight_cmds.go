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
	switch runtime.GOOS {
	case "windows":
		return []string{"curl.exe"}
	default:
		return []string{"curl", "tar"}
	}
}

func requiredCommandsDetail() string {
	return strings.Join(requiredCommands(), ", ")
}
