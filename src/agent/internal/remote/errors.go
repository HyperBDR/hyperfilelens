package remote

import "hyperfilelens/agent/internal/enrollmentclient"

// IsInvalidEnrollmentToken reports heartbeat failures caused by an invalid token.
func IsInvalidEnrollmentToken(err error) bool {
	return enrollmentclient.IsInvalidEnrollmentToken(err)
}
