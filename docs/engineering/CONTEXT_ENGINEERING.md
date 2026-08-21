# CONTEXT_ENGINEERING — Context Budget, State Restoration, & Session Continuity (Bible)

> **General Conceptual Document (Bible).** For this repository's application (read-path, /sync, entry points) see → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
Engineering that enables an agent to **restore the correct task context with minimal tokens**, ensuring next sessions can seamlessly resume even if the current session disconnects. The **disk is the source of truth**, not memory.

## 1. Read Path & Context Budget
Do not bulk-read all documents at session start. Read **only the entry points** in order (from briefest to most detailed):
1. Compressed Entry Point (1-minute context) → 2. Current Status → 3. Next Work (rolling plan) → 4. Recent Incremental Log.
- Open detailed files (designs, rules, scenarios, dated plans, archives) **on-demand** only when modifying them.
- Enforce **line budgets** on entry-point documents (e.g., brief ≤60 lines, status/plan/log ≤120 lines). Separate excess content into archives/tidy docs.
- Key concept: The entry point is a **map, not a comprehensive manual**. Use links to navigate to details.

## 2. Knowledge Pyramid
| Layer | Nature |
| --- | --- |
| L0 | Entry points read unconditionally at session start. |
| L1 | Core references consulted immediately when needed (designs, rules, plans). |
| L2 | Task-specific details (dated plans, design docs, structured work items). |
| L3 | Large, generated, or lookup files (reviews, reports, traces, archives) — kept out of default context. |

## 3. Three-tier State Storage
| Layer | Medium | Question Answered |
| --- | --- | --- |
| Change History | git history | What was changed? |
| Structured State | Machine-readable ledger (work/event log) | How did the loop execute? |
| Natural Language State | Status, progress, and handoff documents | Why? What next? |
These three are complementary. None of them replaces the others completely.

## 4. Session Continuity (Resume Pointer) — Plan-only/Incomplete Handoff
If a session ends plan-only or incomplete and the next session must resume it:
1. **Define a single "next session" pointer at the very top of the entry point** containing the in-repo plan path + first concrete action.
2. Elevate that task as the **authoritative active focus**, aligning the entry point, status, and plan documents (do not leave it as just a footnote).
3. The state restoration procedure must bubble up this pointer **first**, allowing the next session to resume seamlessly. Clear or update it once resumed.
- **Forbidden**: Do not write scratch paths (random names, machine-local paths) created outside the session as the authoritative pointer — next sessions will not be able to resolve them.

## 5. Entry Point Divergence Prevention
Keep multiple agent entry points (instruction files for different tools) aligned by keeping **one common body and using links in the others**. Copy-pasting instructions soon leads to divergence. Standardize on thin wrappers pointing to a single source of truth.

## 6. Sister Concepts (Bibles)
- Parent Harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md)
- Multi-Agent: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md) · Prompt Layer: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This Repo Application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
