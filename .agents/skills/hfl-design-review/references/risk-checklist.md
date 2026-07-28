# HyperFileLens Risk Checklist

Read only the sections relevant to the proposed change. Use the checklist to discover decisions and verification needs, not to force every item into the final response.

## Cross-cutting scope

- Identify affected runtime components: Django API, Celery, Channels, Vue console, Go Agent, Nginx, PostgreSQL, Redis, Kopia, SourceLens, installer, or release pipeline.
- Trace the authoritative source of state and every consumer of a changed contract.
- Distinguish control-plane state, Agent-local state, repository state, generated artifacts, and cached state.
- Preserve existing tenant, platform-operations, and administrator boundaries.
- Define observability, audit records, error details, and operator recovery for new failure modes.
- Check behavior during partial rollout, restart, timeout, retry, cancellation, and duplicate delivery.

## Backup, restore, and destructive operations

- Define the protected or restored object precisely, including source, snapshot, repository, path, and organization identity.
- Establish idempotency and duplicate-request behavior for every state-changing operation.
- Define lease, timeout, cancellation, retry, and partial-success semantics.
- Decide what survives backend, worker, Agent, host, or network interruption.
- Preserve repository integrity when a task loses ownership or receives a late result.
- Require explicit confirmation for destructive actions and make the affected scope visible.
- Ensure retention, deletion, unregister, reset, and overwrite behavior cannot target a broader scope than intended.
- Record durable task and audit outcomes even when execution fails after partially changing external state.
- Verify restore paths, platform path rules, permissions, overwrite policy, and recovery from incomplete output.

## Agent and control-plane protocols

- Identify the wire message, API, package, environment, and persisted-state contracts being changed.
- Define compatibility between older Agents and newer control planes, and the reverse when supported.
- Decide whether a protocol capability requires negotiation, versioning, or a safe fallback.
- Specify delivery guarantees, acknowledgement timing, replay behavior, ordering, and duplicate handling.
- Define offline persistence, reconnect behavior, watchdog renewal, and terminal-result reconciliation.
- Keep authoritative node identity and organization binding stable through reinstall, repair, rebind, and gateway routing.
- Test malformed, missing, unknown, late, and repeated frames without corrupting task state.

## Authentication, tenancy, and sensitive data

- Scope every query, mutation, event, task, cache key, and WebSocket group by the correct organization or platform boundary.
- Verify authorization independently of UI visibility and client-provided identifiers.
- Preserve CSRF, session, OAuth, enrollment, and token lifecycle guarantees.
- Prevent passwords, cookies, tokens, API keys, access keys, OAuth codes, verification codes, and private configuration from entering logs, errors, UI details, audit payloads, or clipboard text.
- Use the repository's shared error-detail sanitization and notification mechanisms.
- Consider enumeration, replay, confused-deputy, and cross-tenant reference attacks.
- Define revocation and cleanup behavior for disabled users, Agents, credentials, and integrations.

## Database, API, and configuration contracts

- Define migration ordering, defaults, nullability, backfill cost, locking risk, and rollback limitations.
- Support mixed application versions during rolling or interrupted upgrades when the deployment model permits them.
- Preserve existing data or document an explicit, confirmed migration or removal policy.
- Check API request, response, pagination, error, idempotency, and status-code compatibility.
- Avoid changing defaults silently when existing installations rely on them.
- Follow configuration precedence: command line, process environment, repository `.env`, then `.env.example` defaults.
- Keep generated templates, installer configuration, runtime Compose files, and documentation aligned.

## Frontend workflows

- Follow the applicable `src/frontend/AGENTS.md` rules and reuse existing shells, navigation, components, styles, API wrappers, notifications, and error sanitization.
- Cover loading, empty, error, and success states for remote data.
- Prevent stale asynchronous results and duplicate submissions.
- Provide localized English and Chinese user-visible strings where the repository requires them.
- Make destructive scope, validation failures, long-running task handoff, and recovery actions clear.
- Preserve complete business values and configuration summaries instead of silently truncating or omitting them.
- Verify light and dark themes, relevant responsive layouts, and keyboard-accessible interactions.

## Installation, upgrade, and release

- Preserve the supported OS, architecture, Docker, Compose, and host-tool matrices.
- Keep offline installation genuinely offline after artifacts are prepared.
- Maintain pinned versions, checksums, package identity, and reproducible artifact metadata.
- Define preflight checks, finite timeouts, retries, resumability, and actionable failure messages.
- Preserve existing Docker installations unless the documented lifecycle explicitly allows modification.
- Verify pre-upgrade backup creation, validation, retention, and recovery behavior.
- Define rollback when database, configuration, image, Agent package, or gateway changes have partially completed.
- Keep development, release, installer, and Data Gateway paths consistent where they share contracts.

## Verification and acceptance

- Test the smallest unit that owns each decision and the integration boundary that could invalidate it.
- Include compatibility tests for old data, old configuration, old clients, or old Agents when relevant.
- Exercise timeout, retry, duplicate, cancellation, restart, and partial-failure paths for distributed work.
- Verify tenant isolation and sensitive-data redaction with negative tests.
- Validate migrations against representative existing data and document irreversible steps.
- Run the repository's targeted checks first, then broader quality or smoke checks in proportion to risk.
- Express acceptance criteria as observable behavior, including failure and recovery behavior, rather than only implementation details.
