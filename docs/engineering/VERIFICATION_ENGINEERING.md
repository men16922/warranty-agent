# VERIFICATION_ENGINEERING — What Proves a Commit Is Good (Bible)

> **General Conceptual Document (Bible).** Not bound to a specific repository. For this repository's application (gate, critic, manual boundary) see → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
A verification strategy that splits "is this change actually good?" into **three layers by what kind of judgment each requires** — mechanical, semantic, and creative — so that the unattended loop can keep everything a machine or a read-only reviewer can decide, and surface to a human **only** what genuinely needs human judgment. One-line principle: **Automate every check that does not need taste; reserve the human queue for the checks that do.**

This is the organizing axis behind `HARNESS_ENGINEERING §3`'s L1–L5 layers: L1–L3 are *mechanical*, L4 is *semantic*, L5/`[manual]` is *creative*. This bible names the three judgment classes, states what each can and cannot catch, and defines how they compose into the loop's keep/revert decision.

## 1. The Three Layers
| Layer | Who judges | Mechanism | Catches | Cannot catch |
| --- | --- | --- | --- | --- |
| **Mechanical** | Deterministic machine | Offline commit gate (lint + typecheck + build + test), re-run **externally** after each commit | Compile/type errors, failing tests, lint/format, forbidden patterns, contract-test breaks | Anything no test exercises; "passes but wrong"; scope creep; weakened tests |
| **Semantic** | Read-only LLM (critic) | Independent review of the committed diff, no edits | Regressions behind a green gate, scope-creep beyond the task, test subversion (deleted/skipped/loosened), dead-code masking | Subjective quality; aesthetic/balance/UX feel; whether the *idea* is right |
| **Creative** | Human | `[manual]` backlog tag + morning review (`/overnight-report`) | Taste, game balance, UX/visual feel, product/judgment calls, strategy | (nothing automatable — this is the residue by design) |

The layers are a **filter cascade**: mechanical is cheapest and runs always; semantic runs on top (opt-in, risk-gated); creative is the human residue. Each layer removes work the next would otherwise have to do — the goal is to shrink the human queue to only what is irreducibly human.

## 2. Composition in the Loop (keep / repair / revert)
Rejection is **two** decisions, not one: *whether* to reject, and *whether the diagnosis is worth handing back*.
```
commits → external re-gate ─RED→ repairable ─┐   ┌→ repair edge (bounded, opt-in):
            └GREEN→ critic ──┬─ repairable ──┼───┘  return the reject evidence to the
                             ├─ violation ───┼→ REVERT + count failure   actor for one fix,
                             └─ PASS → verifiers → KEPT       ↑           then re-run this
                                          └─ reject ──────────┘           WHOLE cascade
```
- **Mechanical is a hard gate, not a soft signal.** An agent reporting success (`is_error:false`) is *not* proof; the gate is re-run externally at the new commit. A RED here is a **phantom-success**.
- **Semantic is fail-closed.** The critic rejects only on concrete diff evidence, but an unparseable/uncertain verdict is **inconclusive and rejects**: a silently broken verifier must never auto-accept. (A legacy fail-open switch exists; treat it as a debugging aid, not a default.)
- **Not every rejection is repairable.** A wrong *behavior* (regression, masking) is a bug — name it precisely and the actor can fix it. A broken *agreement* (test deleted/weakened, scope-creep) is not: re-prompting an actor that just gamed the gate invites it to game the reviewer instead. Violations and inconclusive results go straight to revert.
- **The repair edge does not touch the perimeter.** Gate and verifiers re-run on the repaired commit, attempts are hard-capped, an uncommitted tree counts as no fix (never auto-committed), and final rejection reverts **every** commit the iteration made.
- **Creative never blocks the loop.** Work needing taste is *not* in the `[auto]` backlog at all; it is tagged `[manual]` and routed to a human, never gated automatically.

## 3. Per-Project Specialization
Every project tunes all three layers; this is what makes the harness fit a specific codebase:
| Layer | Specialization point | Example |
| --- | --- | --- |
| Mechanical | `gate` command (`harness-config.json`) | `make check` vs `npm test && npm run typecheck` |
| Semantic | `scripts/overnight/CRITIC_PROMPT.md` (per-repo override) + `OVERNIGHT_CRITIC=auto\|1` | "Balance constants must not change without a `[manual]` flag"; "API response contract is invariant" |
| Creative | `[manual]` criteria + morning-review focus (`INTERPRETATION`) | "Any change touching difficulty curves needs human playtest" |

Default semantic critic is generic (regression/scope/subversion/masking). The leverage is **domain invariants**: encode the project-specific "green but wrong" failure modes a generic reviewer would miss into a per-repo `CRITIC_PROMPT.md` (copy `CRITIC_PROMPT.example.md` to activate). Start `OVERNIGHT_CRITIC=auto` (risk-gated, near-zero cost on hygiene commits) and escalate to `1` for high-stakes repos.

## 4. Principles
- **Push work down the cascade.** If a "green but wrong" failure recurs, first try to make it *mechanical* (a regression test) — a deterministic gate beats a probabilistic critic. Only encode it in the critic if no test can express it. Only leave it `[manual]` if no machine and no read-only reviewer can decide it. (Mirrors `HARNESS_ENGINEERING §2`'s feedback ladder.)
- **Thin `[auto]` backlog is a signal, not a bug.** In aesthetic/subjective projects the creative residue dominates; the `[auto]` queue depletes fast and the loop stops with no progress. That is correct — do not lower the bar to manufacture `[auto]` work.
- **Semantic verification is conservative by contract.** A wrongly-rejected good commit costs an iteration and erodes trust. The critic's *bias* is PASS — it earns a rejection only with concrete diff evidence. (Distinct from its *parse-failure* default, which is reject; see §2.)
- **A rejection's diagnosis is the most valuable thing the failure produced — do not discard it.** Reverting and restarting blind makes the next attempt repeat the mistake, and repeated rejections exhaust the failure budget and end the run with nothing. So every verifier must state *what* is wrong in one actionable line, not merely *that* something is. Reviewer independence (role ≠ enough) is `AGENTIC_ENGINEERING §3`.
- **Name what fails where.** Each layer must make its verdict legible (gate log, critic log, repair log, review checklist) so a human can see *which* layer rejected, why, and whether a repair was attempted.

## 5. Non-Goals (Scope Boundary)
These belong to the **host/operator**, not the verification layers or this plugin — recorded here so they are not re-proposed as harness features:
- **Loop kickoff** (cron / CI / GitHub Actions) — the runner is unattended *once started*; scheduling the start is a host concern. Cloud runners also conflict with the local least-privilege model (network/push are blocked by design — `HARNESS_ENGINEERING §4`).
- **External reporting** (Slack / Notion / dashboards) — failure notification is host transport (`notify.sh`); progress lives in repo docs.
- **Automated push** — the loop commits locally only; promotion is a human decision after morning review.
- **Goal/deadline routing ("what not to do today")** — a planning concern above the loop, not a verification layer.

## 6. Sister Concepts (Bibles)
- Parent Harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Autonomous Loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md)
- Multi-Agent: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md) · Context Restoration: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md) · Prompt Layer: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This Repo Application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
