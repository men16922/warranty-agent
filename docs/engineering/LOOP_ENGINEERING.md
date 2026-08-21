# LOOP_ENGINEERING — Autonomous Unattended Loop Operations (Bible)

> **General Conceptual Document (Bible).** For this repository's application (runner, env, make targets) see → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
An execution loop that invokes a single prompt headlessly and repeatedly. In each iteration, it **restores state from a small context → implements one task → passes verification gates → logs progress → commits locally**. One iteration = one atomic unit of work. Since it commits every iteration, **any crash or halt limits loss to at most one iteration's work**.

## 1. Core Principles
| Principle | Reason |
| --- | --- |
| **Fresh context per iteration** | New process for every run → avoids context bloat/summarization issues. Restores state quickly by reading only the Read Path. |
| **1 iteration = 1 task + instant commit** | If token limits or crashes hit at any time, uncommitted loss is limited to 1 iteration. The next iteration picks up the thread. |
| **Offline gate = commit gate** | No commit unless deterministic gates (lint+type+build+test) are green → prevents broken code from piling up. No network required. This is the *mechanical* verification layer (see [`VERIFICATION_ENGINEERING.md`](VERIFICATION_ENGINEERING.md)); an optional *semantic* critic and the *creative* `[manual]` boundary sit on top of it. |
| **State on disk** | Backlog, history, git history. The disk is the source of truth, not memory. |
| **Unattended execution with least privilege** | push, network, and destructive commands are blocked via allow/deny boundaries (`HARNESS_ENGINEERING §4`). |

## 2. Iteration Flow (loop-once)
```
Restore State → Recover Leftovers (interrupted previous runs) → Select 1 Task from Backlog
  → Implement + Pass Gates → Log Progress → Local Commit → (pause) → Repeat
```
- **Recover Leftovers**: A dirty tree at start indicates leftovers from a previous interrupted run. Commit if gates are green, otherwise signal halt without modifications.
- **Classification of Results**: Classify iteration results structurally as success/limit/failure (do not use fragile grep on free text to avoid false positives).
  limit→wait and retry; failure→increment consecutive failure count; success→check HEAD diff to confirm a commit was made, increment no-progress count if none.

## 3. Backlog Tagging — Indicating Unattended Targets
Use automation tags as a **separate axis** from status boxes:
- `auto` = Verifiable locally, deterministically, offline. **One-line definition of done is mandatory** (prevents scope creep).
- `manual` = Requires human feel, aesthetics, or balance assessment → cannot be verified unattended.
- `blocked` = Unmet prerequisites or 2 accumulated Blockers (marked automatically by the runner). Lift only after human review.
- No Tag = Not for unattended run (security default). The runner only consumes `auto*`; never elevate arbitrarily.
> **Thin backlog is normal**: In repositories with highly subjective/aesthetic tasks, `auto` backlog depletes quickly. Terminating with no progress is normal. To improve efficiency, **seed** `auto` tasks (regression backfills, codemods, lint/type debt, stale doc cleanups) before running.

## 4. Exit Conditions (Backstop)
Backlog depleted (DONE) · Manual/red leftovers (STOP) · Max iterations reached · Consecutive failures count · No progress count. **Stop immediately when done** (costs 0 extra tokens).

## 5. Limits of Applicability
This loop is suitable for **hygiene, regressions, refactoring, codemods, and deterministic bugfixes**. Do not use it for creative, aesthetic, or content generation tasks — unattended gates cannot verify them (mark them `manual` for human QA).

## 6. Sister Concepts (Bibles)
- Parent Harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Commit verification (gate/critic/manual): [`VERIFICATION_ENGINEERING.md`](VERIFICATION_ENGINEERING.md) · Multi-engine parallel: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md)
- Context Restoration: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md) · Iteration Prompt: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This Repo Application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
