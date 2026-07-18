package enroll

import (
	"bufio"
	"fmt"
	"os"
	"runtime"
	"strings"
)

func platformDescription() string {
	detail := osPrettyName()
	if detail == "" {
		return fmt.Sprintf("%s/%s", runtime.GOOS, runtimeArch())
	}
	return fmt.Sprintf("%s/%s (%s)", runtime.GOOS, runtimeArch(), detail)
}

func osPrettyName() string {
	switch runtime.GOOS {
	case "linux", "darwin":
		return readOSReleasePrettyName()
	case "windows":
		return readWindowsCaption()
	default:
		return ""
	}
}

func readOSReleasePrettyName() string {
	f, err := os.Open("/etc/os-release")
	if err != nil {
		return ""
	}
	defer f.Close()

	pretty := ""
	name := ""
	versionID := ""
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		switch {
		case strings.HasPrefix(line, "PRETTY_NAME="):
			pretty = strings.Trim(strings.TrimPrefix(line, "PRETTY_NAME="), `"`)
		case strings.HasPrefix(line, "NAME="):
			name = strings.Trim(strings.TrimPrefix(line, "NAME="), `"`)
		case strings.HasPrefix(line, "VERSION_ID="):
			versionID = strings.Trim(strings.TrimPrefix(line, "VERSION_ID="), `"`)
		}
	}
	if pretty != "" {
		return pretty
	}
	if name != "" && versionID != "" {
		return name + " " + versionID
	}
	return name
}

func readWindowsCaption() string {
	return "Windows"
}
