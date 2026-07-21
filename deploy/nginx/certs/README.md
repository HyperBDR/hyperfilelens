# HyperFileLens default TLS certificates

This directory contains the repository-pinned TLS identity used by default for
local development, CI, bundled SourceLens, and release installations.

## Files

- `tls.crt`: HyperFileLens server certificate.
- `tls.key`: matching server private key. This key is intentionally public and
  provides encryption compatibility, not a unique deployment identity.
- `root-ca.crt`: root certificate that signed `tls.crt`.
- `SHA256SUMS`: pinned checksums verified while building release packages.

The root CA private key is not included in this repository and must never be
committed. Rotation requires an offline signing key or a new root CA. Release
checks reject every private key except the exact pinned `tls.key` file above.

## Names covered by the default server certificate

The certificate covers `localhost`, `hfl.localhost`,
`hyperfilelens.localhost`, `*.hyperfilelens.localhost`,
`host.docker.internal`, `hfl.test`, `hyperfilelens.test`,
`*.hyperfilelens.test`, `127.0.0.1`, and `::1`. It intentionally contains no
production IP address or public domain. `.test` names require local DNS or
hosts-file entries.

## Trusting the default root CA

Installing `root-ca.crt` in a client's trusted root store removes the browser
warning only when the URL also matches a covered name.

On Ubuntu or WSL:

```bash
sudo cp root-ca.crt /usr/local/share/ca-certificates/hyperfilelens-root-ca.crt
sudo update-ca-certificates
```

On Windows, import the separately published `hyperfilelens-root-ca.crt` into
the Local Computer **Trusted Root Certification Authorities** store, then
restart the browser.

Because the default server private key is public, externally reachable or
security-sensitive deployments should atomically replace `tls.crt` and
`tls.key` with a deployment-specific pair. Keep the canonical filenames.
Install and upgrade preserve an existing complete pair and fail when only one
of the two files is present.
