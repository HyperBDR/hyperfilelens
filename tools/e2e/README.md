# Gateway Chat E2E

`test-gateway-chat.sh` is a manually invoked, production-guarded integration
test. It creates three text fixtures below an existing backup root, triggers a
real backup, restores the selected path through each requested Data Gateway,
creates a Copilot Chat, checks that the AI answer contains all fixture values,
and tears down Chat-owned resources. The Backup Config, Snapshot, and
Repository remain intact.

Authentication must be supplied through `HFL_E2E_ACCESS_TOKEN` or an existing
Netscape-format cookie file; secrets are never accepted as command arguments.

```bash
HFL_E2E_ACCESS_TOKEN='...' ./tools/e2e/test-gateway-chat.sh \
  --base-url https://192.168.8.69:11443 \
  --environment test \
  --insecure \
  --org-key example-org \
  --backup-config-id 1 \
  --gateway-link-id 1 \
  --gateway-link-id 2 \
  --fixture-root /srv/hfl-nas/nfs/e2e
```

The fixture root must already be covered by the selected Backup Config. The
tool refuses known production hosts unless both `--environment production` and
`--allow-production` are supplied.
