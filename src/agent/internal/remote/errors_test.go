package remote

import (
	"errors"
	"testing"
)

func TestIsInvalidEnrollmentToken(t *testing.T) {
	if !IsInvalidEnrollmentToken(errors.New(`heartbeat HTTP 401: {"error":"invalid enrollment token"}`)) {
		t.Fatal("expected invalid token")
	}
	if IsInvalidEnrollmentToken(errors.New("connection refused")) {
		t.Fatal("unexpected match")
	}
}
