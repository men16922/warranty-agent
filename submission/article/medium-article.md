# Your remediation agent says "completed." Mine says whether it helped.

### Building an accountability ledger for agent fleets on Google Cloud — with ADK, Cloud Run, Cloud Monitoring, and Firestore. Including the four times the system failed its own test.

![warranty](https://raw.githubusercontent.com/men16922/warranty-agent/main/submission/gallery/logo.png)

---

You gave a fleet of agents access to production. This morning you open the log.

```
✔ 03:14  agent-7   shifted traffic       completed
✔ 03:21  agent-2   changed concurrency   completed
✔ 03:44  agent-7   shifted traffic       completed
   …  eleven more                        completed
```

Fourteen green lines. Every action succeeded.

And the service is exactly as slow as it was last night.

**"Completed" is not "improved."** Restarting succeeds while the error rate stays flat. Scaling
returns `200` while p95 gets worse. Shifting traffic works while the real cause sits somewhere
else. In all three the logs are the same shade of green, and the agent has no way to tell the
difference.

Here is why it cannot: **nobody wrote down what "better" would look like** for that resource.

That knowledge exists exactly once — at provisioning time. The person (or agent) who created the
service knew which signal meant health and how to undo the change. Then they moved on, the doc
rotted, and the Day-2 agent had to re-derive it. Mostly it guesses.

**Verification built on a guessed signal is not verification.** A guessed rollback plan is wrong
on the day you need it.

---

## The idea: the contract is born with the resource

`warranty` is an operations agent with one structural difference: **the agent that provisions a
resource also emits its operational contract in the same step.**

Not a runbook. Not a wiki page. A record, in Firestore, next to the thing it describes:

```json
{
  "contract_id": "demo-target-warranty-v2",
  "resource":    { "kind": "cloud_run_service", "name": "demo-target",
                   "region": "us-central1" },
  "health_signal": {
    "kind":            "cloud_monitoring",
    "metric_type":     "run.googleapis.com/request_latencies",
    "aggregation":     "P95",
    "window_s":        120,
    "resource_filter": "demo-target"
  },
  "recovery_criterion": { "direction": "decrease", "mode": "relative",
                          "threshold": "0.20", "tolerance": "0.05" },
  "rollback_plan": { "kind": "cloud_run_traffic",
                     "previous_revision": "demo-target-00001-swl",
                     "verify_traffic": true },
  "reversibility": "reversible",
  "state": "active"
}
```

Four things the Day-2 agent no longer has to guess: **which signal means health**, **what counts
as recovery**, **where to roll back to**, and **whether rolling back is even possible.**

![Architecture. Day 1 writes the contract; Day 2 reads it. The gate is deterministic code — the model picks the tool and judges only the ambiguous verdicts.](https://raw.githubusercontent.com/men16922/warranty-agent/main/submission/gallery/01-architecture.png)
*Architecture. Day 1 writes the contract; Day 2 reads it. The gate is deterministic code — the model picks the tool and judges only the ambiguous verdicts.*

---

## The loop: act, wait, re-measure

When the agent remediates, it does six things:

1. Reads the **contract's** signal as a baseline — not a signal it picked.
2. Runs a decision gate on three axes: **reversibility × verifiability × budget headroom.**
3. Executes.
4. **Waits.** Longer than the measurement window. (More on this below — it is where we were
   wrong for days.)
5. **Re-measures the same signal, the same way.** Same filter, same aligner, same window.
   Different aligners would make the two numbers incomparable.
6. If it did not recover: rolls back, **re-measures again**, and **reads the traffic split back
   from Cloud Run.**

That last clause matters more than it looks.

```
rollback:
  performed:        true
  signal_restored:  true
  verified_traffic: { "demo-target-00001-swl": 100 }
```

Not *"I rolled back."* But *"I rolled back, and here is the server telling me it is 100 percent
on the healthy revision."* **That is a measurement, not a claim.**

This is the one place where committing to Google Cloud instead of a neutral abstraction actually
buys something. A Cloud Run traffic split is **one API call, atomic, and readable back.** On a
generic VM you would have to build all three of those properties yourself, and the third one is
the one everybody skips.

![The loop, and the three verdicts it can produce.](https://raw.githubusercontent.com/men16922/warranty-agent/main/submission/gallery/02-the-loop.png)
*The loop, and the three verdicts it can produce.*

---

## The policy: if we cannot verify it, we do not automate it

The gate asks three questions, and the second one is the unusual one:

| Axis | Question |
|---|---|
| Reversibility | Can I undo this? |
| **Verifiability** | **Can I measure whether it worked?** |
| Budget headroom | Can I afford it, and is there room left today? |

Most gates model only reversibility. But **an action you can undo and cannot measure is still an
action you should not automate** — you will not know whether to undo it.

A freshly provisioned service is the clean case. It has no previous revision to return to, and
its signal has no data points yet:

```
Gate Verdict : MANUAL
Exact Rule   : irreversible and not verifiable
Executed     : false
```

The executor was never called. Not "tried and failed" — **never called**, and the row says so.

---

## What it actually did, on a real service

Here is a real round trip against the deployed agent. A bad deploy has pushed traffic to a
revision that serves at 900 ms instead of 620 ms.

**It fixed it:**

```
Gate Verdict        : AUTO  (reversible and verifiable within budget)
Signal Before       : 990.04 ms
Signal After        : 674.17 ms
Verification Verdict: recovered
Rollback Occurred   : false
```

**And on the next action, it made things worse — and undid itself:**

```
action_id       : traffic:demo-target-00002-lss
decision        : AUTO
baseline        : 674.17 ms
after           : 990.04 ms      ← worse
verdict         : not_recovered
rollback        : performed true
signal_restored : true
verified_traffic: { "demo-target-00001-swl": 100 }
```

Same shape of action. Two different verdicts. **The ledger says which is which.**

![A real production response: 990 ms → 674 ms, recovered, no rollback needed.](https://raw.githubusercontent.com/men16922/warranty-agent/main/submission/gallery/03-it-fixed-something.png)
*A real production response: 990 ms → 674 ms, recovered, no rollback needed.*

![The other direction: 674 ms → 990 ms, rolled back — and confirmed from the server, not from memory.](https://raw.githubusercontent.com/men16922/warranty-agent/main/submission/gallery/04-it-rolled-itself-back.png)
*The other direction: 674 ms → 990 ms, rolled back — and confirmed from the server, not from memory.*

---

## The ledger is the product

The agent is not the interesting part. Plenty of things can shift traffic. What is missing from
most agent stacks is the row that gets written afterward:

```
entry        kind    target                          status    decision  verification    rollback  attribution  cost
01m17nq…     action  traffic:demo-target-00001-swl   executed  AUTO      recovered       —         none         0
01m17ja…     action  traffic:demo-target-00001-swl   executed  AUTO      not_recovered   true      none         0
01m17cw…     action  traffic:day1-demo-final-00001   manual_required  MANUAL  —          —         none         0
```

`executed`, `improved`, and `rolled_back` are **three separate columns**, and the daily report
derives them rather than storing them:

```
Executed 14 · Improved 1 · Rolled back 12 · Manual required 3
```

A tool that counts only completions reports **fourteen successes**. This one says it helped once.

**Most of those twelve rollbacks are ours** — we generated them while testing this system. We are
not clearing the ledger to make the ratio look better. That would be the exact thing this project
argues against.

!["improved" is the only column that had to be earned twice — once by acting, once by measuring.](https://raw.githubusercontent.com/men16922/warranty-agent/main/submission/gallery/05-the-report.png)
*"improved" is the only column that had to be earned twice — once by acting, once by measuring.*

The ledger has a read view: the deployed service serves it at `GET /`. Read-only, no buttons,
nothing to install. It is not a control plane — it is a receipt.

![The live page, served by the agent itself on Cloud Run. Read-only — there is no button here.](https://raw.githubusercontent.com/men16922/warranty-agent/main/submission/gallery/06-live-ledger-page.png)
*The live page, served by the agent itself on Cloud Run. Read-only — there is no button here.*

### The cost column, and the honest zero

Every row carries a cost and an **attribution method**, and the second one is the one that
matters:

- `resource_label` — the agent stamped a label on the created resource, and **read it back**.
  That row can be found in the bill.
- `token_meter` — computed from token counts and a published rate. Real, but not a billing line.
- `none` — we cannot attribute it, **and we say so** instead of printing a number we cannot check.

Traffic-shift actions cost `0`, with the reason `no billable resource created`. That zero is
correct: shifting traffic between existing revisions creates nothing billable. We resisted the
urge to make it look bigger.

---

## The part where the system failed its own test. Four times.

Here is the section I would skip if I were selling something.

On the last day of the build, I set out to record the scene above — the one where the agent
actually *fixes* something. **It never came.** Shifting traffic back to the healthy revision kept
returning `not_recovered`. Four separate causes, and **every one of them looked green in the
logs.**

### 1. The re-measurement window still held the past

```python
VERIFY_DELAY_S  = 45    # wait after acting
VERIFY_WINDOW_S = 120   # then read a 120-second window
```

Wait 45 seconds, then read the last 120 seconds — and **75 seconds of that "after" is before the
action.** The mixture erases the improvement. Verification was structurally tilted toward
failure, and had been since the beginning.

The fix is a one-line invariant, and it is now a guard:

```python
VERIFY_DELAY_S = VERIFY_WINDOW_S + 15   # the window must not contain the past
```

### 2. The recovery threshold was unreachable

The contract asked for a **60% drop** (`threshold 0.5 + tolerance 0.1`). The injected fault can
only ever produce **31%** (900 ms → 620 ms).

**No action could ever be called recovered.** A failure report from a judge that cannot pass
anything is not information.

The live proof: `990.04 → 674.17 ms` — a **32% improvement** — reported `not_recovered`.

Two guards now, because lowering the bar has its own failure mode:

```python
def test_a_perfect_fix_can_actually_be_called_recovered():
    # policy must be below physics, or "not_recovered" carries no information
    assert threshold + tolerance < best_possible_improvement()

def test_doing_nothing_is_still_not_recovered():
    # ...and not so low that a no-op scores
    assert threshold > tolerance
```

### 3. The contract kept the old policy after we fixed the code

Changing the constant changed nothing. **Policy lives in the contract**, by design — a contract
is a record of what was agreed, not a pointer to whatever the code says today. Changing policy
means **issuing a new contract version**, which is what the `-v1` suffix was always for.

This one cannot be covered by a mutation, because the offline test gate never opens Firestore.
So it lives in the record instead of in a guard, and we say that out loud.

### 4. Waiting longer killed the request before the verdict came home

Making the agent wait 135 seconds instead of 45 pushed the **rollback path** to
`2 × 135s + model round trips`. Cloud Run's request timeout is **300 seconds** — a value we got
by *not writing one*.

```
upstream request timeout
```

The action shipped. The ledger was correct. **Only the answer was lost.** That is the quietest
failure of the four: nothing in the logs, nothing in the ledger, just a caller who never learned
what happened.

```python
WAITS_PER_REMEDIATION = 2          # after the action, and after the rollback
REQUEST_TIMEOUT_S = 2 * WAITS_PER_REMEDIATION * VERIFY_DELAY_S
```

…and a second guard, because a constant that never reaches the deploy is a sentence nobody reads:

```python
def test_the_deploy_actually_carries_that_timeout():
    assert f"--timeout={REQUEST_TIMEOUT_S}" in deploy_argv(...)
```

![All four looked green in the logs. Three are now guards with mutations; the fourth is in the record.](https://raw.githubusercontent.com/men16922/warranty-agent/main/submission/gallery/07-it-failed-its-own-test.png)
*All four looked green in the logs. Three are now guards with mutations; the fourth is in the record.*

### How we found them

Not from logs. **From staring at two numbers that should not have disagreed** — `990` and `674`,
sitting next to the word `not_recovered`.

A system built to argue that *executing is not improving* could not read its own improvement.
That is either the most embarrassing thing in this project or the most convincing one, and I have
decided it is the second.

---

## How it is built

- **ADK + Gemini 3.7 Flash on Vertex AI** — four tools: `provision`, `inspect`, `remediate`,
  `report`. The model picks the tool; **the decision is not the model's.** The gate is
  deterministic code. The model is asked only to judge the *ambiguous* verification band — and
  when it does, its rationale is written into the ledger row.
- **Cloud Run** — both the agent and the demo target, `min-instances=0`. Rollback is a traffic
  split, which is why it is atomic and why it can be read back.
- **Firestore** — contracts and ledger. `create()` rather than `set()`, so "one action, one row"
  is enforced by the database instead of by convention.
- **Cloud Monitoring** — p95 request latency, read with the same filter, aligner and window for
  the baseline and the re-measurement.
- **Ports and adapters** — the offline test gate runs the entire narrative against fakes with
  **zero billable calls**, and a tripwire fails the build if a live client is so much as
  *constructed* during the gate.

The repo is spec-driven, and the spec is enforced rather than decorative:

- a requirement marked `IMPLEMENTED` must have a test targeting **every sentence** it promises;
- a requirement marked `VERIFIED` must have a **mutation** confirmed to turn the suite red;
- `make check` fails when a status claim outruns reality.

At the time of writing: **447 tests, 285 mutations, all confirmed red.**

Mutation testing is what caught three of my own patterns going stale this week: I moved a
constant to another module and the mutation aimed at it silently stopped applying. A mutation
that no longer applies **keeps its "confirmed" status for free** — the harness now checks for
exactly that, because the alternative is a guard that quietly guards nothing.

---

## What I would not claim

- **This is correlation, not causation.** Re-measuring after a rollback is a weak natural
  experiment. It does not establish cause.
- **Contracts exist only for resources the agent provisioned.** A hand-made resource is not an
  automation target — the gate returns `MANUAL` and means it.
- **A signal read while two revisions serve is ambiguous.** During a traffic split, Cloud
  Monitoring returns one series per revision, and our reader takes the latest point — on a tie,
  whichever came back first. It settles once traffic converges. We know the shape of the fix; we
  have not built it.
- **The recovery rate is a recovery rate *by our criterion*.** If the contract's criterion is
  wrong, the verification is wrong with it. We know, because ours was.

---

## Try it

The ledger page is public and read-only — no login, nothing to install:

**[https://warranty-api-povpqj6m5a-uc.a.run.app/](https://warranty-api-povpqj6m5a-uc.a.run.app/)**

Code: **[github.com/men16922/warranty-agent](https://github.com/men16922/warranty-agent)**
Demo video (3:47): **[https://youtu.be/KAcHpX3nSSM](https://youtu.be/KAcHpX3nSSM)**

---

If you take one thing from this: **add the second column.** Whatever your agents do, the log line
that says `completed` is the cheap half. The expensive half is the one that had to be earned
twice — once by acting, and once by going back to measure.

*Built for the Google All Things Agentic Hackathon, Fortified Enterprise Fleet track.*
