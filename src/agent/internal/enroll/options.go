package enroll

// InstallOptions controls non-interactive enrollment behavior.
type InstallOptions struct {
	AutoYes bool
}

// ParseInstallOptions reads flags after `hfl-enroll install`.
func ParseInstallOptions(args []string) InstallOptions {
	opts := InstallOptions{}
	for _, a := range args {
		switch a {
		case "--yes", "-y":
			opts.AutoYes = true
		}
	}
	return opts
}
