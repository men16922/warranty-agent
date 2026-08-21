# PROMPT_ENGINEERING — Agent & LLM Prompt Design (Bible)

> **General Conceptual Document (Bible).** For this repository's application (iteration prompt, narrative prompt) see → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
Engineering that **constrains and guides** agent and LLM behavior using prompts. There are generally two layers:
① **Harness Prompt** (fixed procedure executed by the agent every iteration)
② **Runtime/Domain Prompt** (requests made by the product feature to the LLM).

## 1. Harness Iteration Prompt
Define the fixed procedure executed by the unattended loop every iteration in the prompt:
- Standard procedure: restore state → recover leftovers → select 1 task → implement+gate → log → commit.
- Engine-specific branching: Tailor prompts to each engine's capabilities (skill calling support, sandboxing constraints) even when executing the same procedure.
- **Elevate prompt-based constraints to deterministic gates whenever possible** (Feedback Ladder, `HARNESS_ENGINEERING §2`). Prompt-based constraints are a last resort (only for things the sandbox cannot block). Do not explicitly forbid fabrication (passing gates with fake artifacts).

## 2. Runtime/Domain Prompt — Reliability Patterns
| Pattern | Content |
| --- | --- |
| **Structured Output** | Force schema-based output (e.g., JSON) instead of free text, and define constraints (length, number of items, allowed keys). |
| **Model Specialization** | Separating generation (free text, large model) and structuring (parsing, small model) improves reliability. |
| **repair → fallback** | Attempt 1 repair on parsing failure → fall back to a **deterministic fallback** (user-visible or safe action) on repeated failure. |
| **context selection** | Avoid injecting the entire codebase; inject only relevant snippets + rollups/summaries (prevents context bloat, cost, and drift). |

## 3. Tone/Register Rules are in the "Feel" Domain
Aesthetic tone, register, and repetition suppression belong to the **human judgment (feel)** domain and cannot be locked down with a deterministic gate. Document these rules (e.g., scene-by-scene registers, repetition guidelines) but verify via human QA. repetition is often a real issue; suppress it via prompt guidelines + recent context window.

## 4. Sister Concepts (Bibles)
- Parent Harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md)
- Multi-Agent: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md) · Context: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md)
- This Repo Application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
