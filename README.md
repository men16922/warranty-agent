# fleet-ledger

**An agent fleet's ledger — attributing cloud spend to the actions that caused it.**

> Google All Things Agentic Hackathon · Fortified Enterprise Fleet track
> Submission deadline: 2026-09-01 09:00 KST

---

## The problem

Agent observability watches tokens, latency, and errors. It does not watch **the money the
agent spends**. And estimates of that spend are wrong in the reassuring direction:

> We once costed a monitoring pipeline at **$2–7/month**. Then we measured the cluster:
> **52,438 time series** where the estimate assumed "a few hundred." The unit prices were
> right. The *quantity assumption* was off by about **100×**.

## What this does

Every action an agent takes writes one ledger row. The row carries **what we assumed it cost**
and, once the billing data lands a day later, **what it actually cost** — side by side, never
overwritten. The difference is the product.

It also does something most tools don't: **it measures its own budget gate's error rate.**
The gate decides with estimates, and this project exists because estimates are wrong — so the
gate's accuracy is itself a first-class output.

## Status

🚧 **Design complete, implementation not started** (2026-08-19).

## Start here

| | |
|---|---|
| **What must be true** | [`specs/fleet-ledger/requirements.md`](specs/fleet-ledger/requirements.md) ← highest authority |
| **Why this shape** | [`specs/fleet-ledger/design.md`](specs/fleet-ledger/design.md) |
| **What to build next** | [`specs/fleet-ledger/tasks.md`](specs/fleet-ledger/tasks.md) |
| Decisions + rejected alternatives | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Contest facts | [`docs/HACKATHON.md`](docs/HACKATHON.md) |

**This repo is spec-driven**: the spec is the source of truth. If the code disagrees with the
spec, the code is wrong. A guard (G6) fails the build when a requirement has no test.

## Provenance

Built from scratch during the Submission Period. I maintain a separate personal project
(`platform-agent`) in the same problem space; **no code from it is used here.** The design
judgments carried over — and only the judgments — are written out in prose in
[`docs/REFERENCE_FROM_PARENT.md`](docs/REFERENCE_FROM_PARENT.md).
