# AGENTIC_ENGINEERING — Multi-Agent Parallel Operations (Bible)

> **General Conceptual Document (Bible).** For this repository's application (3 engines, worktrees, make targets) see → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
Engineering that coordinates multiple headless agents using **roles, isolation, and gates** to collaborate without conflicts. A single agent does not do everything. An orchestrator decomposes and assigns tasks, and specialized agents execute in their respective domains.

## 1. Prevent Conflicts through "Structure"
Do not rely on intent to prevent concurrent edit conflicts; use **isolation**. Keep three axes disjoint:
1. **Worktree Isolation** — Different worktrees and branches for each agent → prevents editing the same file concurrently.
2. **Lane Separation** — Tag backlog tasks with agent suffixes → prevents two agents from claiming the same item.
3. **Domain Splitting** — Directory ownership per agent → makes merge conflicts virtually non-existent.
4. **Shared Doc Protocol** — Documents modified by multiple agents should be append-only + merge=union, or toggle a single line in their own lane.

## 2. Role Specialization (Builder ≠ Reviewer ≠ Researcher ≠ QA)
| Role | Responsibility |
| --- | --- |
| Orchestrator | Decomposes tasks, assigns lanes, integrates results, resolves conflicts, and gives final approvals. |
| Builder | Implements, refactors, writes tests, and passes verification gates. |
| Reviewer | Conducts read-only audits of git diffs (bugs, edge cases, missing tests, drift). **Does not edit code**. |
| Researcher | Researches, analyzes documentation, and generates drafts (images, content). |
| QA | Verifies E2E, browser, and screenshots. |
Roles are not free (they incur token and coordination overhead). For small repositories, it is reasonable for the Builder to also act as the Orchestrator.

## 3. Creator ≠ Reviewer (Core Loop)
Separate the creator agent from the reviewer agent to reduce **confirmation bias**:
```
Builder creates/modifies → Integrates → Reviewer read-only audit → Feeds findings back to backlog → Builder modifies
```
The reviewer does not edit the code or the backlog directly — they only produce findings. The orchestrator reflects them in the backlog.

**Independence has three axes and role is only the first** — a reviewer sharing the builder's engine cannot see what that engine systematically misses, so role separation alone leaves the most expensive failure (a bad change **accepted**) partly unguarded:
| Axis | Removes | Still shared |
| --- | --- | --- |
| **Role** — read-only, separate prompt | incentive to approve one's own work | blind spots |
| **Model** — different tier | some capability-specific misses | tooling, vendor priors |
| **Engine** — different CLI/vendor | tool surface + vendor blind spot | (residue is `[manual]`) |

Cross the engine where a second CLI exists. And a reviewer that *cannot run* is a **failed verification perimeter**, not an optional step: fail loudly at startup rather than quietly falling back to the builder's own engine.

## 4. Deterministic vs Non-Deterministic Lanes have Different Gates
- **Deterministic (Code)**: Gate green → auto-commit. Safe.
- **Non-Deterministic (Images/Content/Feel)**: Same input yields different outputs and relies on "feel" judgment → cannot be locked down with a deterministic gate.
  → Auto-commit based only on **integrity gates** (exists, fits specification), and verify aesthetic/narrative quality via **human review**. Do not fabricate missing assets.

## 5. Reasoning Sandwich
Planning = high reasoning, implementation = medium reasoning, verification = high reasoning. Using the highest-tier model for all steps is wasteful. Match model tiers to each step.

## 6. Sister Concepts (Bibles)
- Parent Harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Single Loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md)
- Context Restoration: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md) · Prompt Layer: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This Repo Application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
