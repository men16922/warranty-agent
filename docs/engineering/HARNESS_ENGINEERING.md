# HARNESS_ENGINEERING — Agent Operations Harness Scaffolding (Bible)

> **General Conceptual Document (Bible).** Not bound to a specific repository. For this repository's application (Interpretation) see → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
An operations framework that embeds **knowledge, constraints, verification, state tracking, and review loops inside the repository** to allow safe, iterative agent execution, rather than letting AI agents write code unchecked. One-line principle: **Humans steer. Agents execute.**
Humans define directions, boundaries, and exceptions; agents iterate on implementation, verification, modification, and logging within them.

## 1. Maturity Ladder (L0→L4)
| Level | Definition |
| --- | --- |
| L0 Ad-hoc | Human approval required for every action; rules and state exist only in the chat context. |
| L1 Basic Harness | Agent instructions file + lint/test gate + worktree/branch isolation + plan documentation. |
| L2 Automated Feedback | Gate scripts + independent reviewer + auto-retry on failure + checkpoint logging. |
| L3 Multi-Agent | Separate coder/reviewer/gardener roles + risk-based approval + parallel worktrees + regular entropy scans. |
| L4 Self-Evolving | Failure trace analysis + automated harness-improving PRs + human intervention only for exceptions. |
Most projects target **L2→L3** as a realistic goal. Self-diagnose your level and invest only in the next gap.

## 2. Feedback Ladder — Leverage Repeated Feedback into Stronger Systems
| Frequency | Encoding Target |
| --- | --- |
| 1st time | Review notes |
| 2nd time | Documentation |
| 3rd+ times | Script / Linter / Test (Deterministic Gate) |
| Safety Breach | Hard gate (Block) |
Key concept: If a feedback point is repeated, lock it down as a **deterministic gate** instead of prose.

## 3. Verification Layers — Deterministic First, Probabilistic on Top
| Layer | Trigger | Catches |
| --- | --- | --- |
| L1 | File change | Forbidden patterns, file size limits, secrets, conflict markers. |
| L2 | Turn end | Lint, format, typecheck, architecture/dependency rules. |
| L3 | Pre-completion | Unit, integration, contract tests. |
| L4 | Post-L3 | LLM/Codex read-only review (bugs, edge cases, drift). |
| L5 | PR/Merge | Full CI, E2E, human approval. |
Establish L1-L3 (deterministic) first, then layer L4 (probabilistic review) on top. They can be combined into a single gate command or split into scripts — **just make it clear what fails where**.

## 4. Tier-based Boundary Security — Boundaries, Not Micro-Approvals
| Tier | Action |
| --- | --- |
| 1 Always Allowed | read, grep, glob, git status/diff |
| 2 Allowed in Repo | edit src/tests/docs/scripts + listed safe commands + local commit |
| 3 Conditional (Block/Human) | push, network requests, destructive commands, secrets, prod, dependency installation |
Tier 3 requires a plan before execution (what to do, reason, impact, recovery, command). The unattended environment **physically blocks** Tier 3.

## 5. Adoption Principles
- **Repository as SoT**: Rules and state live in the repository, not in chat memory. Plans live in-repo (no scratch paths).
- **Agent Legibility First**: Keep entry points small, core docs short, and details linked. Enforce restrictions via tests/scripts.
- **Constraints Create Speed**: Specifying "what not to do" reduces guessing and drift, making execution faster.
- **Progressive Deletability**: Add a **deprecation condition** to every rule/gate (e.g., 3 months without violation, equivalent CI verification, or architecture mismatch).
- **Agent-friendly errors**: Gate failures must contain 4 elements (what/where/why it is forbidden/how to fix) so agents can self-correct.
- **Diagnose before fixing**: Establish root causes with evidence before attempting fixes (reproduce → hypothesize → measure → fix → re-measure). Do not mark "fixed" without measurement — shallow fixes that loop in circles are the highest agent friction. Enforce the protocol using the `/diagnose` skill. (Deprecation condition: 3 months without recurrence of the same friction.)

## 6. Three-tier State Storage
git history (change history) + structured ledger (work/event log) + natural language (status, progress, handoff docs).
The disk is the source of truth, not memory → restore working context from a fresh context for each run.

## 7. Sister Concepts (Bibles)
- Autonomous Loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md) · Multi-Agent: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md)
- Context Restoration: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md) · Prompt Layer: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This Repo Application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
