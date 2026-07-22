package enroll

import (
	"context"
	"fmt"

	"hyperfilelens/agent/internal/platform/hostinfo"
)

func platformDescription() string {
	info := hostinfo.Collect(context.Background())
	if description := info.Description(); description != "" {
		return description
	}
	return fmt.Sprintf("%s/%s", info.OSFamily, info.Arch)
}
