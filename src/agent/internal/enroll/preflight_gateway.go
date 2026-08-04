package enroll

type gatewayRuntimePreflightResult struct {
	ExistingDocker bool
	Detail         string
	RequiredSpace  uint64
	Warnings       []string
	Err            error
}
