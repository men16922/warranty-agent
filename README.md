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

## The number most tools never print

```
executed · improved · rolled back · unverifiable
```

Most tools count `executed` and call it success. **`improved` is a different column**, and it
can be smaller. The ledger owns the counts — this page does not restate them.

## Status

**Running on Cloud Run.** An ADK agent on Gemini 3.7 Flash **provisions** Cloud Run services
and records their operational contract in the same step, reads Cloud Monitoring, shifts Cloud
Run traffic, and writes contracts and the ledger to Firestore — all behind the live URL below.

| | |
|---|---|
| Repository | https://github.com/men16922/warranty-agent |
| **★ Accountability ledger (open this first)** | **`https://warranty-api-povpqj6m5a-uc.a.run.app/`** — read-only, no login |
| Live API | `https://warranty-api-povpqj6m5a-uc.a.run.app` |
| Public health probe | `curl https://warranty-api-povpqj6m5a-uc.a.run.app/livez` → `200` |
| `POST /agent:chat` | bearer token required — no token or a wrong one returns `401` |
| Demo target | `https://demo-target-povpqj6m5a-uc.a.run.app/work` |

⭐ **The first link is the agent's own page.** It renders the ledger: `executed` next to
`improved`, and the cost **attribution** next to the amount — `resource_label` means that row
can be found in the bill, `none` means it cannot, and we say which. It is read-only: there is
no button on it, nothing is stored, and that is why it needs no login.

⚠️ **The signal only exists while traffic flows.** Both services scale to zero, so with no
load the p95 window holds no samples and the agent answers *"I cannot read this right now"*
rather than *"healthy"*. That is the policy working, not a fault — put load on
`demo-target/work` first if you want to watch a recovery.

Evidence for every live claim above is in [`docs/evidence/`](docs/evidence/); what is still
open is in [`specs/warranty/tasks.md`](specs/warranty/tasks.md).

## Start here

| | |
|---|---|
| **What this is, in full** | [`docs/OVERVIEW.md`](docs/OVERVIEW.md) ← diagrams, data flow, status |
| **Architecture diagram** | [System architecture](docs/OVERVIEW.md#4-아키텍처) ← canonical submission artifact |
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
make demo                   # the narrative end to end — deterministic, offline
make trace                  # spec traceability matrix
```
