---
name: hfl-design-review
description: Review ambiguous or high-risk HyperFileLens requirements and designs before implementation, expose consequential decisions, and produce an implementation-ready decision brief. Use automatically for backup or restore correctness, Agent-control-plane protocols, authentication or tenant isolation, database migrations, public APIs or configuration, offline installation or upgrades, destructive operations, or changes spanning multiple components. Also use when the user explicitly invokes hfl-design-review or asks to challenge, grill, clarify, or stress-test a design. Do not use for localized bugs with clear reproduction steps, copy- or style-only edits, test-only changes, or mechanical refactors unless explicitly invoked.
---

# HyperFileLens Design Review

Stress-test consequential requirements without turning routine work into an interview. Investigate the repository first, ask only for decisions that cannot be derived safely, and converge quickly.

## Follow the review workflow

1. **Honor the requested mode.** Distinguish review-only work from review-then-implement work. Do not write code when the user asks only for analysis. When implementation is requested, complete the proportionate review and then continue unless a genuinely blocking decision remains.
2. **Inspect before asking.** Read every applicable `AGENTS.md`, the relevant implementation and tests, and any API, deployment, or configuration files that can answer the question. Use repository evidence to identify current behavior and constraints. Preserve unrelated worktree changes.
3. **Classify the risk.** Use the levels below. For high-risk work, or medium-risk work touching a listed domain, read [references/risk-checklist.md](references/risk-checklist.md) and apply only the relevant sections.
4. **Build the decision tree.** Separate repository facts, safe assumptions, reversible choices, and consequential unresolved choices. Ask the user only about the final category.
5. **Ask efficiently.** Lead with the evidence and the recommended choice. Ask one to three independent questions per round and no more than two rounds. Use a structured input tool when available and suitable; otherwise ask concise plain-text questions. Prefer two or three concrete, mutually exclusive options when the decision space is known, but use an open question when fixed choices would distort the answer. Always allow the user to accept the recommendation.
6. **Checkpoint and converge.** After each round, briefly state confirmed decisions, assumptions, and remaining blockers. Stop interviewing when critical branches are resolved, the user accepts the recommendations, two rounds are complete, or the remaining decisions are reversible and can be handled with stated assumptions.
7. **Deliver or proceed.** Produce the decision brief below. If implementation was requested, proceed using the agreed decisions and verify the change in proportion to its risk. If the request was review-only, stop after the brief.

## Classify risk

- **Low:** Localized, reversible, single-component work that changes no contract, persistent data, security boundary, or destructive behavior. Do not interview; state any minor assumption and proceed.
- **Medium:** A bounded behavior or interface change whose wrong default would cause meaningful rework. Ask at most one round of questions, and only when the answer materially changes the implementation.
- **High:** Work involving possible data loss, backup or restore semantics, distributed Agent behavior, authentication or tenant isolation, secrets, destructive actions, schema migration, backward compatibility, public contracts, installation or upgrade behavior, or multiple runtime components. Inspect the relevant checklist sections and resolve consequential ambiguity before implementation.

## Apply questioning guardrails

- Ask for product intent, acceptable tradeoffs, compatibility promises, operational policy, or authority that the repository cannot establish.
- Do not ask the user to locate files, repeat documented behavior, choose implementation trivia, or answer facts discoverable from the codebase.
- Do not block on a preference when a safe, conventional, reversible default exists. State the default and continue.
- Do not silently assume behavior that could cause data loss, cross-tenant exposure, incompatible protocol or schema changes, an unsafe upgrade, or an irreversible external effect.
- Do not expand the requested scope merely because the review exposes adjacent improvements. Record them as non-goals or follow-up work.
- Do not continue questioning after the exit conditions are met.

## Produce a decision brief

Keep the brief proportional to the task and include:

- Goal and user-visible outcome
- Non-goals and preserved behavior
- Repository evidence and affected components
- Confirmed decisions and stated assumptions
- Contracts, data, compatibility, security, and failure-recovery implications when relevant
- Implementation outline
- Verification and acceptance criteria
- Remaining risks or follow-up work

For a low-risk task, compress this to a few sentences. For high-risk work, make every consequential decision traceable to evidence, a user answer, or an explicit safe default.
