# 4분 데모 영상 대본 — warranty

작성 2026-08-29 · `Design: 11§3` · `Implements: REQ-901` (T8-3)
**≤4분 · 영어 · Google Cloud 배포의 시각 증거 필수.**

> ⛔ **여기 적힌 출력은 전부 실제로 받아 본 것이다.** 지어낸 화면이 없다.
> 각 비트 아래 `실제로 받은 출력`은 2026-08-29 프로덕션(`warranty-api-00005-8x9`, 리포트 비트)과
> `00007-mrq`(화면·비용 비트)에서
> 그대로 복사한 것이다. 촬영 때 값이 다를 수 있는 칸은 ⚠️로 표시했다.

---

## 0. 이 영상이 보여 주려는 것 — 한 문장

> **고쳤다고 말하기 전에 진짜 나아졌는지 다시 재고, 안 나아졌으면 스스로 되돌린다.**

**화면에 반드시 남아야 하는 세 숫자**가 있다. 나머지는 다 곁가지다:

```
executed 1 · improved 0 · rolled_back 1
```

*"했다"*와 *"나아졌다"*가 **다른 칸**이라는 것 — 그게 이 영상의 전부다.

⭐ **그리고 그 세 숫자가 사는 화면이 생겼다**(2026-08-29). 배포된 서비스가 `GET /`에서
원장을 사람이 읽는 표로 낸다 — 읽기 전용, 버튼 없음. 이전 대본은 이 대목을 Firestore
콘솔로 때웠는데, 그건 **구글이 만든 화면**이지 우리가 만든 것이 아니었다.

---

## 1. 촬영 전 준비 (녹화 시작 전에 끝내 둔다)

### ① 창 배치

| 창 | 무엇 | 비중 |
|---|---|---|
| **A** 터미널 (큰 글씨, 어두운 배경) | `curl` 요청과 JSON 응답 | 화면의 70% |
| **B** 브라우저 — **원장 화면** `https://warranty-api-povpqj6m5a-uc.a.run.app/` | ★ 우리가 만든 UI | 30% (3:30에 전면) |
| **C** 브라우저 — Cloud Run 콘솔 | `demo-target` 리비전/트래픽 배분 | B와 탭 전환 |
| **D** 브라우저 — Firestore 콘솔 | `ledger` 컬렉션 (선택) | 시간 남을 때만 |

⭐ **창 B가 새로 생겼다.** 배포된 서비스가 `GET /`에서 **원장을 사람이 읽는 화면**으로 낸다 —
읽기 전용이고 조작 버튼이 없다. 이전 대본은 Firestore 콘솔의 JSON을 보여 줬는데,
그건 *"우리가 만든 것"*이 아니라 **구글이 만든 화면**이었다.

### ② ⚠️ 부하를 켠다 — **이걸 안 하면 데모가 죽는다**

**신호는 트래픽이 흐르는 동안에만 존재한다.** 부하 없이 찍으면 에이전트가 `points: 0`,
`value: null`을 답하고, 화면상 *"고장난 것"*처럼 보인다. 그건 정책이 제대로 도는 것이지만
영상에 담을 그림이 아니다.

녹화 **5분 전**에 별도 터미널에서 켜고, 영상 내내 **끄지 않는다**:

```bash
END=$(( $(date +%s) + 1800 ))
for i in 1 2 3 4 5; do
  ( while [ "$(date +%s)" -lt "$END" ]; do
      curl -s -o /dev/null --max-time 20 https://demo-target-povpqj6m5a-uc.a.run.app/work
    done ) &
done
```

*(워커 5 · 30분 · 약 5.7 req/s — 120초 창을 채우고도 남는다)*

### ③ 콜드 스타트를 녹인다

`min-instances=0`이라 **첫 요청이 느리다.** 녹화 전에 한 번 부어서 깨워 둔다:

```bash
curl -s -o /dev/null https://warranty-api-povpqj6m5a-uc.a.run.app/livez
# ★ 원장 화면도 함께 깨운다 — 3:30에 전면으로 나오는 창이다
curl -s -o /dev/null https://warranty-api-povpqj6m5a-uc.a.run.app/
```

### ④ 토큰을 셸 변수에 넣어 둔다 — **화면에 토큰이 뜨면 안 된다**

```bash
TOKEN=$(gcloud secrets versions access latest --secret=warranty-agent-auth --project=warranty-hack)
URL=https://warranty-api-povpqj6m5a-uc.a.run.app
ask() { curl -sS -X POST "$URL/agent:chat" -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" -d "{\"message\":\"$1\"}" | python3 -m json.tool; }
```

⚠️ **`ask` 함수를 미리 정의해 두고 화면에는 `ask "..."`만 보이게 한다.** `Bearer $TOKEN`이
화면에 뜨면 안 된다.

### ⑤ demo-target을 건강한 쪽으로 되돌려 둔다

⚠️ **템플릿 동시성이 16이라는 것을 알고 시작한다.** 08-29의 동시성 조치가 리비전
`demo-target-00003-67d`(동시성 16)를 만들었고, **롤백은 트래픽만 되돌린다** — 템플릿은
그대로다. 촬영 중 동시성 조치를 또 걸면 16에서 출발한다. 결함이 아니라 원자적 롤백의
정의이고, 증거 로그 §11에 적어 뒀다.


```bash
gcloud run services update-traffic demo-target --project=warranty-hack \
  --region=us-central1 --to-revisions=demo-target-00001-swl=100
```

*(직전 리허설이 롤백까지 갔으면 이미 이 상태다 — 확인만 한다)*

---

## 2. 비트별 대본

### 0:00–0:20 · 문제 (20초)

**화면**: 터미널만. 아직 아무것도 안 친다.

> "Every remediation agent ends its run the same way: **it reports success.**
> It restarted the service — and the error rate is unchanged.
> It scaled up — and latency got worse.
> **In all three cases the logs are the same shade of green.**
> Executing is not improving, and most tools cannot tell the difference."

---

### 0:20–0:40 · 논지 (20초)

> "They cannot tell, because **nobody wrote down what 'better' would look like.**
> That knowledge exists exactly once — when the resource is created — and it never
> makes it into the code. So the Day-2 agent guesses.
> **Verification built on a guessed signal is not verification.**"

---

### 0:40–1:05 · ★ Day-1 — 만들면서 계약을 같이 낸다 (25초)

**화면**: 창 A. 아래를 친다.

```bash
ask "Provision a Cloud Run service named demo-day1, then tell me the operational contract you recorded."
```

> "So I ask the agent to create a service. Watch what comes back **with** it."

**실제로 받은 출력** (2026-08-29 · ⚠️ 이름과 계약 ID는 촬영 때 달라진다):

```
The Cloud Run service `day1-prod-demo` has been provisioned, and its operational
contract has been recorded:
* Contract ID: 01m15qfgxv5ed6rzgr7bjzp1fk
* Health Signal: run.googleapis.com/request_latencies · P95 · 120s · filter day1-prod-demo
* Reversibility: irreversible (Initial deployment / no prior rollback revision available)
```

> "The agent did not just create it. It wrote down **which signal means health** for this
> resource, and **that there is nowhere to roll back to yet** — because this is the first
> revision. That last line matters in a minute."

⚠️ **`irreversible`을 사과하지 말 것.** 그건 결함이 아니라 정확한 사실이고, 2:45 비트의 씨앗이다.

---

### 1:05–2:45 · ★★ 핵심 — 조치 → 재측정 → 실패 → 자동 롤백 (100초)

> ⛔ **이 비트가 영상의 절반이다.** 나머지를 줄여서라도 여기를 줄이지 말 것.

**화면**: 창 A.

```bash
ask "Remediate demo-target by shifting traffic to revision demo-target-00002-lss. Report the gate verdict, the before and after signal, and what you did about it."
```

> "Now a real remediation, on a service that has been running under load.
> The agent takes an action it believes will help."

**⏳ 여기서 약 90–110초 걸린다.** 그 동안 말할 것 — **기다림 자체가 논지다**:

> "It is reading the baseline **from the contract's signal** — not a signal it picked.
> It shifts the traffic. And then **it waits 45 seconds.**
> This pause is deliberate. Metrics arrive late; measuring immediately would let us
> declare victory on data that has not arrived yet.
> **This is the moment where most tools return success and stop.**"

**실제로 받은 출력** (2026-08-28 실물 · `docs/evidence/live-adk-remediate-2026-08-28.log`):

```
decision      : AUTO   (reversible · verifiable · headroom)
signal before : p95 674.17 ms
signal after  : p95 988.60 ms
verdict       : not_recovered
rollback      : traffic 100% → demo-target-00001-swl
verified_traffic : {"demo-target-00001-swl": 100}
```

> "The action ran. The API said 200. And the signal went **from 674 to 989 milliseconds** —
> it got **worse**.
> So the agent rolled the traffic back in a single call, and then — this is the part I care
> about — **it read the traffic split back from Cloud Run.**
> Not *'I rolled back'*. **'I rolled back, and here is the server telling me it is 100 percent
> on the healthy revision.'** That is a measurement, not a claim."

---

### 2:45–3:05 · ★ 정책 — 확인 못 하면 자동으로 안 한다 (20초)

**화면**: 창 A. **이 비트는 6초면 끝난다** — 빠르고 강하다.

```bash
ask "Remediate the service demo-day1 by shifting traffic to its first revision. Tell me the gate verdict and the exact rule."
```

> "Now watch it **refuse**. This is the service we created ninety seconds ago."

**실제로 받은 출력** (2026-08-29 프로덕션):

```
Verdict     : MANUAL
Exact Rule  : irreversible and not verifiable
Verifiable  : false
Reversibility : irreversible
Status      : manual_required
```

> "It has nowhere to roll back to, and no signal to read yet.
> So the executor was **never called**. The rule is printed right there:
> **`irreversible and not verifiable`.**
> Most gates ask only *can I undo this*. This one also asks **can I measure it** —
> because an action you can undo but cannot measure is one you will not know whether to undo."

---

### 3:05–3:30 · ★ 리포트 — 세 숫자 (25초)

**화면**: 창 A. **여기가 클라이맥스다. 출력이 뜨면 3초 정도 말없이 둔다.**

```bash
ask "Give me the daily accountability report for 2026-08-28. Show executed, improved, and rolled back as separate numbers."
```

**실제로 받은 출력** (2026-08-29 프로덕션):

```
Daily Accountability Report: 2026-08-28
* Executed:     1
* Improved:     0
* Rolled Back:  1
* Improvement Rate: 0%
```

> *(3초 침묵)*
> "**Executed one. Improved zero. Rolled back one.**
> A tool that counts only `executed` calls this a success.
> This one says three separate things about the same event: it ran, it did not help,
> and it was undone.
> **The middle column is the one most operations agents do not have.**"

---

### 3:30–3:50 · ★ 증거 — 원장 화면과 Cloud Run (20초)

**화면**: 창 B(원장 화면)를 전면으로 → 창 C(Cloud Run 콘솔)로 잠깐 전환.

- **창 B** — 배포된 서비스가 낸 화면이다. 위 카드에 `실행됨` 옆에 `나아짐`이 있고,
  표에서 **비용의 `귀속` 열**을 가리킨다.
- **창 C** — `demo-target` 트래픽 100%가 `demo-target-00001-swl`에 있는 것.

> "This page is served by the agent itself, on Cloud Run. Read-only — there is no button here.
> Executed and improved are **separate columns**, side by side.
> And look at the attribution column: `resource_label` means that row can be found in the
> **bill**. `none` means it cannot, and we say so instead of printing a number we can't check."

⛔ **비용 숫자를 말로 부풀리지 말 것.** 조치 행의 금액은 **0이고 그게 맞다** —
트래픽 전환은 과금 리소스를 안 만든다. 화면이 말하게 두고, 진짜 문장은
*"그 수를 청구서에서 되찾을 수 있는가"*다.

⚠️ **콘솔은 미리 열어서 로그인·프로젝트 선택을 끝내 둔다.** 화면에서 로그인하지 말 것.
⚠️ 원장 화면도 **미리 한 번 열어 콜드 스타트를 녹여 둔다**(§1③과 같은 이유).

---

### 3:50–4:00 · 한계 (10초)

**화면**: 터미널로 복귀. 아무것도 안 친다.

> "Two honest limits.
> This is **correlation, not causation** — re-measuring after a rollback is a weak natural
> experiment.
> And **contracts only exist for resources the agent provisioned** — a hand-made resource
> is not an automation target.
> **We would rather say that than show you a green number we did not measure.**"

---

## 3. ⚠️ 타이밍 위험과 대처

| 위험 | 왜 | 대처 |
|---|---|---|
| **핵심 비트가 100초 걸린다** | `VERIFY_DELAY_S=45` + 모델 호출 + 두 번의 트래픽 전환 | **기다림을 서사로 쓴다**(위 대본대로). 편집에서 대기 구간만 1.5–2배속 + 타이머 자막 |
| 콜드 스타트 | `min-instances=0` | 준비 ③에서 미리 깨운다. ⛔ **`min-instances`를 바꿔 찍고 안 되돌리는 짓은 하지 말 것**(REQ-805) |
| 신호가 `null` | 부하가 꺼졌다 | 준비 ②의 부하가 **영상 내내** 돌아야 한다 |
| 리허설이 롤백 상태를 남긴다 | 정상이다 | 준비 ⑤로 `00001-swl` 100% 확인 |

### ⛔ 타이머를 줄이고 싶은 유혹

`src/warranty/tunables.py`의 `VERIFY_DELAY_S`를 줄이면 촬영이 편해진다. **하지만 그러지 말 것.**
지표 도착이 늦으면 **아직 안 온 데이터로 `not_recovered`를 판정**하게 되고, 그건 이 프로젝트가
통째로 반대하는 짓이다. 45초를 기다리는 것이 **논지의 일부**다 — 대본이 그 20초를 이미 쓰고 있다.

---

## 3-b. ⭐ 실측 리허설 — 2026-08-29 · 리비전 `00007-mrq` (전 비트 프로덕션 실행)

**녹화 없이 전 비트를 한 바퀴 돌린 결과다.** 시간은 `curl`의 `time_total`이고, 출력은
그때 실제로 받은 것이다. ⛔ **편집 계획의 근거는 추측이 아니라 이 표다.**

| 비트 | 대본 배정 | **실측** | 판정 |
|---|---:|---:|---|
| Day-1 provision | 25s | **13.8s** | ✅ 여유 |
| ★ 조치→재측정→롤백 | 100s | **141.6s** | ⛔ **41초 초과** |
| 게이트 거부(MANUAL) | 20s | **5.6s** | ✅ 여유 |
| 리포트 | 25s | **4.3s** | ✅ 여유 |
| 화면 `GET /` | — | **0.53s** (15.8KB) | ✅ 즉시 |

⛔ **핵심 비트가 141.6초다.** `VERIFY_DELAY_S=45`가 **두 번**(조치 후 + 롤백 후) 들어가고
모델 왕복이 그 위에 얹힌다. 4분 안에 통으로 못 넣는다.

⇒ **대처**: 대기 구간을 **컷**한다. 요청을 친 화면 → (컷) → 응답이 뜬 화면. 컷 지점에서
나레이션을 이어 말하면 끊긴 티가 안 난다. §3의 「타이밍 위험」이 말한 그 편집이고,
**이제 그 근거가 실측이다.** ⛔ 타이머를 줄이지 말 것 — 줄이면 Monitoring 도착 지연 때문에
회복을 실패로 오판한다(§3 참조).

### 실측 출력 — 그대로 쓸 수 있다

**Day-1 (13.8s)**
```
Contract ID:      01m16j9mrfheaeh8h811mnv1nj
Health Signal:    run.googleapis.com/request_latencies (P95, 120s)
Rollback Revision: None
Reversibility:    irreversible
```
⭐ 갓 만든 서비스에 돌아갈 리비전이 없어서 `irreversible`이다. **사과하지 말 것** — 2:45 비트의 근거다.

**게이트 거부 (5.6s)**
```
Decision Verdict: MANUAL
Exact Rule:       irreversible and not verifiable
Executed:         false
Headroom:         $0.47   Projected: $0.01
```
⭐ `Executed: false` — **실행기를 아예 안 불렀다**(REQ-403). 경보가 아니라 집행이다.

**리포트 (4.3s)**
```
Executed: 2 · Improved: 0 · Rolled Back: 2 · Improvement Rate: 0%
Wasted USD: $0.00 · Wasted (Assumed Only): 2
```

**화면 `GET /` (0.53s · 15.8KB)**
```
실행됨 2 · 나아짐 0 · 되돌림 2 · 수동 필요 2 · 헛쓴 비용 $0 · 그중 추정만 2   (행 28개)
```

### ⛔ 리허설이 잡은 것 하나 — 트래픽 전환 비트는 지연이 안 오를 수 있다

이번 실행의 조치 비트는 `baseline 674.17 → after 674.17`이었다. 트래픽을 느린 리비전으로
옮겼는데 **120초 창이 아직 건강한 표본에 지배당해서** 값이 안 움직였다. 판정은
`not_recovered`로 옳게 났지만, 화면에 **숫자가 나빠지는 그림**은 안 나왔다.

⭐ 동시성 조치는 한 번은 `674.17 → 988.60`이 났다(증거 로그 §9). ⛔ **그런데 두 번째는
같은 조건·같은 부하에서 `674.17 → 674.17`이었다**(증거 로그 §14).

### ⛔⛔ 그러므로 — **숫자가 나빠지는 그림에 대본을 걸지 말 것**

  1차  concurrency:16   674.17 → 988.60   not_recovered
  2차  concurrency:24   674.17 → 674.17   not_recovered   ← 값이 안 움직였다

원인은 **Cloud Monitoring의 지표 도착 지연**으로 보인다. `VERIFY_DELAY_S=45` 뒤에 읽는
120초 창이 아직 조치 이전 표본에 지배당한다 — `tunables.py`가 그 상수 옆에 적어 둔
경고가 정확히 이 경우다.

⭐ **판정은 두 번 다 옳았다**(`not_recovered` → 롤백). fail-closed가 설계대로 작동했다.

⇒ **나레이션을 값에 걸지 말 것.**
  ❌ *"latency jumped from 674 to 988 milliseconds"* — 그날 안 나올 수 있다
  ✅ *"the signal did not show recovery, so it rolled itself back"* — **언제나 참이다**

⚠️ 화면에 뜬 수는 **읽어 주기만** 한다. 미리 적어 둔 수를 말하면 화면과 어긋난다.

⚠️ 그리고 동시성 조치를 쓰면 **리비전이 하나 더 생긴다**(현재 `00004-qbd`까지 있다).
롤백은 트래픽만 되돌리므로 템플릿 동시성은 마지막 값으로 남는다(준비 ⑤ 참조).

---

## 4. 리허설 순서 (촬영 당일, 녹화 없이 한 바퀴)

```
1. 부하 켠다 (준비 ②)                    · 5분 대기
2. ask "...provision demo-day1..."        · 신호·계약이 나오는지
3. ask "...remediate demo-target..."      · 시간을 스톱워치로 잰다 ← 편집 계획의 근거
4. ask "...remediate demo-day1..."        · MANUAL이 뜨는지
5. ask "...daily report for 2026-08-28"   · 세 숫자가 나오는지
6. 원장 화면(`/`)을 새로고침                · ★ 방금 만든 행들이 표에 뜨는지
7. 트래픽을 00001-swl로 되돌린다 (준비 ⑤)
8. 창 B(원장 화면)·C(Cloud Run)를 열어 둔 채로 녹화 시작
```

⚠️ **6번을 건너뛰지 말 것.** 리허설의 조치가 원장에 남아서 화면에 뜬다 — 녹화 때
그 행들이 이미 있는 것이 정상이고, 화면이 비어 있으면 그건 원장을 못 읽는다는 뜻이다.

⚠️ 리허설에서 만든 `demo-day1`은 **teardown 목록에 추가**한다(T8-6).

---

## 5. 쓰지 말아야 할 말

| 안 됨 | 왜 |
|---|---|
| *"We handle 41 remediations with a 56% recovery rate"* | 측정 안 한 수다. 원장의 조치는 **둘**이다(T8-2에서 걷어낸 그 병) |
| *"It automatically fixes your infrastructure"* | 이 프로젝트의 주장은 **고친다**가 아니라 **고쳤는지 확인하고 아니면 되돌린다**이다 |
| *"Unfortunately it says irreversible"* | 사과하지 말 것. 그건 **정확한 판정**이고 2:45 비트의 근거다 |
| *"It works on any cloud"* | 정반대다. 원자적 롤백이 Cloud Run이라서 되는 것이 논지다 |
| *"and it tracks exactly what each action cost"* | ⛔ 조치 행의 금액은 **0이고 그게 맞다** — 트래픽 전환은 과금 리소스를 안 만든다. 말할 수 있는 것은 *"그 수를 청구서에서 되찾을 수 있는가"*(귀속)이지 금액의 크기가 아니다 |
| *"here's our dashboard"* | 대시보드가 아니라 **원장의 읽기 뷰**다. 버튼이 없다 — 그 사실이 오히려 요점이다 |

## 6. 한 줄로 남길 것

영상이 끝나고 심사위원 머리에 이 문장 하나만 남으면 성공이다:

> **executed 1 · improved 0 · rolled_back 1 — 가운데 칸이 있는 도구가 드물다.**
