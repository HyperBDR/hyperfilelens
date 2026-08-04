package identity

import (
	"crypto/rand"
	"encoding/hex"
)

const installationIDBytes = 20

// NewInstallationID returns a random identity for one installation lifetime.
func NewInstallationID() (string, error) {
	random := make([]byte, installationIDBytes)
	if _, err := rand.Read(random); err != nil {
		return "", err
	}
	return "hfli_" + hex.EncodeToString(random), nil
}
