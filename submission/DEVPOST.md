# Devpost 제출 원고 — warranty

작성 2026-08-29 · 마감 **2026-09-01 09:00 KST**
사실의 권위는 `specs/warranty/requirements.md`와 `docs/evidence/`다. **여기서 수를 세지 않는다.**

> 이 파일은 **폼에 붙여 넣을 답**이다. 이전 판은 폼 필드를 긁어 온 것이었고 답이 아니었다.
> `▶ 사람이 할 일` 표시가 붙은 곳은 내가 못 채우는 칸이다.

---

## ✅ 저장소 — 해결됨 (2026-08-29)

**https://github.com/men16922/warranty-agent** — **public**이라 심사위원이 링크만으로 연다.
private 공유(`testing@devpost.com`·`cloudhackathons@google.com` 초대)는 **필요 없다.**
88 커밋 · 기본 브랜치 `main` · `.env`는 올라가지 않았다(확인함).

## ⛔ 남은 결정 하나 — Hosted URL의 수명

**Hosted URL의 수명**을 정해야 한다. `design 10§6`은 teardown을 **09-02**로 잡았는데,
심사는 그 뒤에 이뤄진다. 크레딧도 **09-06 만료**다. 셋 중 하나를 골라야 한다:
① 09-02에 다 내린다(Hosted URL이 죽는다 — 영상과 코드로만 심사받는다)
② Cloud Run만 09-06까지 남긴다(`design 10§6`이 예비해 둔 길 · scale-to-zero라 유휴 과금 0)
③ 09-06 이후로 크레딧을 연장/전환한다
**②가 기본값으로 보인다** — 유휴 0이고 심사위원이 URL을 열 수 있다.

---

# 1. General info

## Project name (60자)

```
warranty
```

## Elevator pitch (200자)

```
Remediation agents report success. Executing is not improving. warranty makes the agent that
provisions a resource also write down how to verify and undo it - then prove it after acting.
```

*(197자)*

---

# 2. Project details

## About the project

### Inspiration

Every remediation agent we looked at ends its run the same way: **it reports success.**

Restarting succeeds while the error rate stays flat. Scaling returns `200` while p95 latency
gets worse. Shifting traffic works while the real cause sits somewhere else. In all three the
logs are the same shade of green, and the agent has no way to tell the difference — because
**nobody wrote down what "better" would look like** for that resource.

That knowledge exists exactly once: at provisioning time. The person who created the service
knew which signal meant health and how to undo the change. **That knowledge never makes it
into the code.** So the Day-2 agent has to re-derive it, and mostly it guesses.

Verification built on a guessed signal is not verification. A guessed rollback plan is wrong
on the day you need it.

### What it does

**The agent that provisions a resource also emits its operational contract** — health signal,
recovery criterion, rollback plan, reversibility — in the same step. Later, when the same agent
remediates, it:

1. reads the **contract's** signal as a baseline (not a signal it picked),
2. runs a decision gate on three axes: **reversibility × verifiability × budget headroom**,
3. executes,
4. **re-measures the same signal the same way**,
5. rolls back atomically if the signal did not recover — and **reads the traffic split back**
   to prove it, rather than claiming it,
6. writes a ledger row where `executed`, `improved`, and `rolled_back` are **three separate
   columns**.

The policy that falls out of this is one line: **if we cannot verify it, we do not automate it.**
A resource with no contract, or whose signal cannot be read right now, is not an automation
target — the gate returns `MANUAL` and the executor is never called.

That last part is what makes the numbers honest. A real run from the deployed service:

```
executed 1 · improved 0 · rolled_back 1
```

Most tools count `executed` and call it success. **This one can say the action ran, did not
help, and was undone** — and can prove each third of that sentence separately.

### How we built it

- **ADK + Gemini 3.7 Flash on Vertex AI** — four tools (`provision`, `inspect`, `remediate`,
  `report`). The model picks the tool; the *decision* is not the model's. The gate is
  deterministic code, and the model is only asked to judge the **ambiguous** verification
  cases — and when it does, its rationale is recorded in the ledger row.
- **Cloud Run** — both the agent and the demo target. Rollback is a traffic split, which is
  why it is atomic and why it can be *read back*.
- **Firestore** — contracts and the accountability ledger. `create` (not `set`) enforces
  "one action = one ledger row" at the database, not by convention.
- **Cloud Monitoring** — p95 request latency, read with the same filter/aligner/reducer for the
  baseline and the re-measurement. Different aligners would make the two numbers incomparable.
- **Ports and adapters** — the offline gate runs the whole narrative on fakes, with **zero
  billable calls**, and a guard fails the build if any live client is even *constructed*
  during the gate.

The repo is spec-driven and the spec is enforced, not decorative:

- a requirement marked `IMPLEMENTED` must have a test that targets **every sentence** it promises,
- a requirement marked `VERIFIED` must have a **mutation** that was confirmed to turn the suite red,
- `make check` fails when a status claim outruns reality.

### Challenges we ran into

**The guard caught us more often than we caught bugs, and that was the point.**

- A mutation designed to kill a Firestore tripwire **did not die**. The guard's census stored
  functions by bare name, so `LiveContractStore._db` was shadowed by `LiveLedger._db`. The blind
  spot only became visible on the first module with two same-named methods.
- A refactor silently **disarmed eight mutations** — the patterns no longer matched, so they
  never applied. The harness reported "the mutation did not change the file," which is the only
  reason they did not become quietly dead guards.
- We built a mutation that *creates* a forbidden file, and the harness's restore only *copied
  files back*. It deleted the leaf and left an empty `vendor/` directory behind — and the
  residue check looked at the same leaf, so it reported "no residue" while residue existed.
  **Recovery failure and residue reporting were looking at different things.**

And the worst one was in our own front page: it advertised
`executed 41 · improved 23 (56%)` as if measured. **Nothing measured those numbers** — they
were slide values from the video script that had leaked into the README. The real ledger had
two actions. A judge who ran `make demo` would have gotten `executed 1 · improved 0` and seen
the contradiction. We deleted the numbers and kept the shape.

### What we learned

**Verifiability belongs on the decision axis, not in the postmortem.** Reversibility is the
axis everyone models. But an action you can undo and cannot measure is still an action you
should not automate — you will not know whether to undo it.

**A signal only exists while traffic flows.** Both services scale to zero, so with no load the
p95 window holds no samples and the agent answers *"I cannot read this right now"* rather than
*"healthy."* That is the policy working, not a fault — but it means the honest answer and the
demo-able answer are different answers, and we had to say so out loud.

**A freshly provisioned service is `irreversible`.** There is no previous revision to go back
to. Typing "Cloud Run services are reversible" would have produced a contract that is wrong on
the day it matters. So the contract says `irreversible`, and that resource is not an automation
target until it has a revision to return to.

### What's next

- Grant policy for provisioned services — right now the agent creates a resource and
  **deliberately does not give anyone permission to invoke it.** An agent that silently opens
  services to the world cannot be the default; the grant needs to be a decision, not a side effect.
- BigQuery billing export reconciliation, so `assumed` cost can be replaced by `measured` cost
  with the difference kept as a derived value. **The estimate is never overwritten.**
- Per-tenant service accounts and Workload Identity Federation, so the boundary is enforced by
  Google Cloud IAM rather than by a filter in our code.

### Known limits — we do not hide them

- **The verification window can miss the effect.** We ran the same action twice under the
  same load: once the p95 moved `674 → 989 ms`, once it did not move at all. Cloud Monitoring
  ingestion lags the action, so a 120-second window can still be dominated by pre-action
  samples. The verdict was `not_recovered` both times — fail-closed, which is what we want —
  but inside that window we **cannot separate "the action did not help" from "we cannot see
  it yet."** We would rather say that than pick the run that looked better.
- **This is correlation, not causation.** Re-measuring after a rollback is a weak natural
  experiment. It does not establish cause.
- **Contracts only exist for provisioned resources.** Hand-made resources are not automation targets.
- **The recovery rate is a recovery rate *by our criterion*.** If the contract's criterion is
  wrong, the verification is wrong with it.
- **Shared-resource cost attribution is unsolved.** Label attribution is used only where one
  action maps to one resource.

## Built with (최대 25개)

```
google-adk  gemini-3.7-flash  vertex-ai  cloud-run  firestore  cloud-monitoring
cloud-build  artifact-registry  secret-manager  python  mermaid  pytest
mutation-testing  spec-driven-development  ports-and-adapters  sre
```

## "Try it out" links

```
★ Accountability ledger (open this first — no login, nothing to install):
  https://warranty-api-povpqj6m5a-uc.a.run.app/

Live API (public health probe):
  https://warranty-api-povpqj6m5a-uc.a.run.app/livez

Demo target (the service the agent remediates):
  https://demo-target-povpqj6m5a-uc.a.run.app/work

Code repository (public):
  https://github.com/men16922/warranty-agent
```

⭐ **첫 링크가 이 제출물의 얼굴이다.** 배포된 에이전트 자신이 낸 화면이고, 그 안에
`executed` 옆에 `improved`가, 금액 옆에 `attribution`이 있다. **읽기 전용이다** —
버튼이 없고, 조치를 걸 수 없고, 아무것도 저장하지 않는다. 그래서 인증을 안 건다.

> ⚠️ `/agent:chat`은 bearer 토큰이 있어야 한다(무토큰·틀린 토큰은 전부 `401`). 공개 URL이
> 무인 과금 권한이 아니라는 것이 설계 결정이다(D15 · design 08§3.A). 심사위원에게는
> **원장 화면**과 `/livez`, 영상, 그리고 아래 Testing instructions를 준다.
> ⛔ **화면은 읽기 전용이라 공개해도 그 결정과 어긋나지 않는다** — 과금·변경 표면은 여전히 닫혀 있다.

## Video demo link

```
▶ 사람이 할 일 — T8-3. ≤4분 · 영어 · Google Cloud 배포의 시각 증거 필수.
⚠️ 촬영은 demo-target에 부하를 켠 채로 한다 — 신호는 트래픽이 흐르는 동안에만 존재한다.
```

---

# 3. Additional info (심사위원용)

| 폼 항목 | 답 |
|---|---|
| Submitter Type | ▶ 사람이 할 일 (Individual) |
| Country of residence | ▶ 사람이 할 일 (South Korea) |
| Category | **Fortified Enterprise Fleet** |
| Organization | 해당 없음 |
| **What date did you start this project?** | **08-19-26** — 첫 커밋 `741cec5` 2026-08-19 |
| URL to code repo | **https://github.com/men16922/warranty-agent** (public — 별도 초대 불필요) |
| **Reproducible Testing instructions in README?** | **Yes** |
| Hosted project URL | `https://warranty-api-povpqj6m5a-uc.a.run.app` |
| **Which Google SDK?** | **Agent Development Kit (ADK)** · Google GenAI SDK (`google-genai`) |
| **Which Google Cloud Services?** | **Cloud Run** · **Firestore** (+ Cloud Monitoring · Cloud Build · Artifact Registry · Secret Manager) |
| Architecture diagram | `docs/OVERVIEW.md` §4 Mermaid → ▶ PNG로 내보내 첨부 |
| **Which Google AI Models?** | **Gemini 3.7 Flash** (Vertex AI) |
| Startup Prize | 해당 없음 |
| Bonus content / social | ▶ 선택 |

## Testing instructions (심사위원에게만 보인다)

```
Offline — no cloud account, no billing, deterministic:

    make venv && make check     # full gate: types, lint, tests, spec traceability
    make demo                   # the five-step narrative end to end, on fakes
    make trace                  # requirement -> design -> task -> test -> mutation matrix

  `make demo` prints its own caveats: the signal is scripted, so this run is NOT live
  evidence. Everything the gate cannot ask is stated rather than implied.

Live — the deployed service:

    curl https://warranty-api-povpqj6m5a-uc.a.run.app/livez        # 200, public
    curl -X POST https://warranty-api-povpqj6m5a-uc.a.run.app/agent:chat   # 401, on purpose

  The agent endpoint requires a bearer token held in Secret Manager. A public URL is not an
  unattended billing permission - that is a deliberate boundary, not an oversight.

Evidence for every live claim is committed under docs/evidence/ with raw logs:
  deploy-*.log, live-adk-remediate-*.log, live-provision-*.log, live-day1-prod-*.log,
  mutation-sweep-*.log
```

---

# 4. 이게 심사에서 실제로 의미가 있나 — 정직한 판정

`docs/HACKATHON.md` §4의 비중으로 항목별로 본다. **강한 곳과 약한 곳을 같이 적는다.**

## Innovation & Operational Utility — 40%

**강하다.** 이 항목이 이 제출물의 승부처이고, 실제로 가장 잘 맞는다.

- 대부분의 agent observability는 토큰·지연·오류를 본다. **`executed`와 `improved`를 다른
  칸으로 두는 것**은 흔치 않고, 그 둘이 다른 값이라는 것을 실물 원장이 보여 준다
  (`executed 1 · improved 0 · rolled_back 1`).
- **검증 가능성을 판정 축에 올린 것**이 진짜 주장이다. 가역성은 다들 모델링한다. *"되돌릴 수
  있지만 나아졌는지 못 재는 조치"*를 자동화 대상에서 빼는 도구는 드물다.
- **롤백을 주장하지 않고 배분을 되읽어 증명하는 것**은 GCP 전용을 정당화하는 구체적 근거다.
  트랙(Fortified Enterprise Fleet)이 묻는 "무엇을 신뢰할 수 있는가"에 정확히 답한다.

⭐ **2026-08-29에 세 번째 축이 실물이 됐다** — 그 전까지 이 항목의 주장은 **3분의 2뿐이었다.**
`Method.RESOURCE_LABEL`은 테스트에만 있었고 코드가 `fl_entry` 라벨을 리소스에 박은 적이
없었다. 지금은 프로비저닝이 원장 행과 라벨을 함께 내고, **GCP에서 되읽어 확인했다**:
`fl_entry=01m16hev85z5b7b4ykzc73tm95`이 원장 항목 id와 같다. 모델 호출은
`token_meter · $0.00174675`를 갖는다.

⭐ **그리고 이것이 *"이거 Flagger 아니야?"*의 답이다.** Flagger·Argo·Kayenta는 카나리에서
지표를 재고 롤백한다 — ①②는 그들도 한다. **그 롤백이 얼마짜리였는지, 그리고 그 수가
계산값인지 청구서인지는 말하지 않는다.** 그게 ③이고, 화면의 `Attribution` 열이 그것을 보여 준다.

⚠️ **약점 ①**: 규모가 작다. 원장의 조치는 지금 **둘**이다. 심사위원이 *"41건 중 23건 회복"* 같은
큰 표를 기대하면 실망할 수 있다. 그러나 대회 기준 어디에도 규모가 없고(§4 마지막 줄),
**측정하지 않은 큰 수를 적는 것이 정확히 우리가 반대하는 것**이다. 이 긴장은 영상에서
말로 처리해야 한다: *"두 건이다. 그리고 그 두 건에 대해 우리는 세 가지를 따로 말할 수 있다."*

⚠️ **약점 ② — 숨기지 않는다**: `wasted_usd`는 **0이다.** 회복에 실패한 조치가 트래픽 전환이고,
트래픽 전환은 과금 리소스를 안 만들기 때문이다. 그 칸이 0인 것은 **정확한 값이지 미구현이
아니다.** 그리고 `measured`(청구서로 확인된 값)는 아직 하나도 없다 — 결제 내보내기는
하루 지연이 있고 제출 기한 안에 못 들어온다. 그래서 화면은 `resource_label`(되찾을 수 있음)과
`none`(되찾을 수 없음)을 **구분해서** 보여 주지, 금액의 크기를 자랑하지 않는다.

⛔ **`docs/HACKATHON.md` §4가 이 칸의 획득 경로로 `REQ-307`을 적고 있는데 그런 요구사항은
없다**(REQ-3xx는 305까지다). 실제 경로는 REQ-502(셋을 따로) · REQ-402(3축 판정) ·
REQ-303/304(증명된 롤백) · REQ-503/504/505(귀속과 추정≠실측)다. 아래에서 고쳤다.

## Architectural Discipline & Tech Stack — 30%

**가장 강하다.** 여기서 점수를 잃을 이유가 거의 없다.

- 필수 스택 셋(Gemini 3.5+ · Google Agent Framework · Google Cloud 인프라)을 **전부** 쓴다.
- 포트/어댑터가 장식이 아니다: **게이트가 네트워크 없이 전체 서사를 돌리고**, 실물 클라이언트가
  게이트 중에 **생성되기만 해도** 빌드가 red다.
- 상태 주장을 기계가 집행한다: `IMPLEMENTED`는 문장 수만큼 겨냥한 테스트를, `VERIFIED`는
  **지워 보고 red를 확인한 변이**를 요구한다. 요구사항 44종 중 **42종이 VERIFIED**이고 남은
  둘은 선택 범위다.
- 변이 **255종 전부 red 확인** · 복구 후 초록 · 잔여 0. 원본 로그가 커밋돼 있다.

⚠️ **약점**: 이 규율은 **읽어야 보인다.** 4분 영상에서 전달하기 어렵다. README 첫 화면과
`make trace` 한 줄이 이걸 대신해 줘야 한다.

## Demo & Production Readiness — 30%

**중간이다 — 다만 08-29에 한 칸 올라갔다.**

⭐ **화면이 생겼다**(`GET /`). 그 전까지 이 프로젝트의 문장은 `curl`을 아는 사람에게만
도착했다. 배포된 서비스가 원장을 사람이 읽는 표로 낸다 — 읽기 전용, 버튼 없음, 인증 없음:
**심사위원이 링크를 눌러서 보라고 만든 화면**이다. `Executed` 옆에 `Improved`가 있고,
금액 옆에 `귀속`이 있다.

- ✅ `make demo`가 결정론적이고, **자기가 증명하지 않는 것을 출력에 적는다.**
- ✅ 거부(`MANUAL`)와 한계가 화면에 보인다 — Production Readiness는 완벽함이 아니라
  **무엇이 안 되는지 아는가**이고, 이 저장소는 그것을 문서·응답·데모 출력 세 곳에서 말한다.
- ✅ 실물 배포가 있고 증거 로그가 커밋돼 있다.
- ⛔ **영상이 아직 없다**(T8-3). 이 항목의 대부분이 영상에 달려 있다.
- ✅ **저장소 URL이 생겼다** — https://github.com/men16922/warranty-agent (public · 08-29).
- ⚠️ **신호가 트래픽 중에만 존재한다.** 부하 없이 찍으면 에이전트가 `null`을 답하고,
  화면상 *"고장난 것"*처럼 보인다. **부하를 켠 채로 찍어야 한다.**

## 종합

| | |
|---|---|
| **가장 강한 것** | 논지가 하나이고, 그것이 코드·게이트·응답·원장에서 **같은 문장**으로 나온다 |
| **가장 약한 것** | **영상**(T8-3) — 아직 없다. 저장소는 08-29에 해결됐다 |
| **가장 큰 유혹** | 숫자를 크게 보이게 하는 것. 한 번 걸렸고(T8-2), 다시 하면 안 된다 |

**한 줄 판정**: 기술적으로는 이미 제출 가능하고 Architectural Discipline에서 강하다.
남은 위험은 전부 **제출물 자체**(영상·저장소·Hosted URL 수명)에 있다.
