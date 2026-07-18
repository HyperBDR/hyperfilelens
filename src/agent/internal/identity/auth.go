package identity

import "context"

// Credentials holds long-lived enrollment material after successful bootstrap.
type Credentials struct {
	OrgKey string
	NodeID string
}

// ComputeHandshakeSignature derives the WSS handshake signature from enrollment secrets.
func ComputeHandshakeSignature(ctx context.Context, creds Credentials, nonce string) (string, error) {
	_ = ctx
	_ = creds
	_ = nonce
	return "", nil
}

// RefreshToken exchanges a refresh credential for a new session token.
func RefreshToken(ctx context.Context, creds Credentials) (string, error) {
	_ = ctx
	_ = creds
	return "", nil
}
