# warranty

**Infrastructure that ships with a warranty.**

The agent that provisions a resource also writes down how to check it and how to undo it —
then, after it acts, it **re-measures the signal it declared** and **rolls back atomically**
when the action did not actually help.

> Google All Things Agentic Hackathon · Fortified Enterprise Fleet
> Submission deadline: 2026-09-01 09:00 KST

---

## The problem

Remediation agents execute an action and report success. **Executing is not improving.**

Restarting succeeds while the error rate stays flat. Scaling returns `200` while p95 latency
gets worse. Shifting traffic works while the real cause sits somewhere else.
In all three, **the logs are the same shade of green.**

## The thesis

> **What can an agent do once it stops trying to be cloud-neutral?**

A neutral agent can only take actions it can express in every cloud. That is why it executes
and reports success but cannot prove it helped, cannot roll back atomically, and cannot say
what the action cost.

This one is **GCP-only on purpose** — and that is what buys:

| | |
|---|---|
| **Verification** | Cloud Monitoring signals read directly, no normalization loss |
| **Atomic rollback** | Cloud Run traffic split — one call, instant, and **verified by reading the split back** |
| **Per-action cost** | resource labels ride into the billing export |

And one policy most tools never state:

> ⛔ **If we cannot verify it, we do not automate it.**

## The number

```
executed 41 · improved 23 (56%) · rolled back 12 · unverifiable 3
```

Most tools count `executed` and call it success.

## Status

🚧 **Design complete, implementation in progress** (2026-08-19).

## Start here

| | |
|---|---|
| **What this is, in full** | [`docs/OVERVIEW.md`](docs/OVERVIEW.md) ← diagrams, data flow, status |
| **What must be true** | [`specs/warranty/requirements.md`](specs/warranty/requirements.md) ← highest authority |
| **Why this shape** | [`specs/warranty/design.md`](specs/warranty/design.md) |
| **What to build next** | [`specs/warranty/tasks.md`](specs/warranty/tasks.md) |
| Decisions + rejected alternatives | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Engineering principles | [`docs/PRINCIPLES.md`](docs/PRINCIPLES.md) |

**This repo is spec-driven.** The spec is the source of truth; if the code disagrees, the code
is wrong. A guard (G6) fails the build when a requirement's declared status is not backed by
reality — `IMPLEMENTED` needs a test, `VERIFIED` needs a mutation confirmed to turn the suite red.

```bash
make venv && make check     # offline, deterministic, no billable calls
make trace                  # spec traceability matrix
```
