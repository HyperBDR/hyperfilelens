package remote

import "strings"

// IsInvalidEnrollmentToken reports heartbeat failures caused by a used or invalid token.
func IsInvalidEnrollmentToken(err error) bool {
	if err == nil {
		return false
	}
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "invalid enrollment token") ||
		strings.Contains(msg, "401") && strings.Contains(msg, "token")
}
