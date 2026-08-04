package enrollmentclient

import "strings"

// IsInvalidEnrollmentToken reports heartbeat failures caused by an invalid token.
func IsInvalidEnrollmentToken(err error) bool {
	if err == nil {
		return false
	}
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "invalid enrollment token") ||
		strings.Contains(msg, "401") && strings.Contains(msg, "token")
}
