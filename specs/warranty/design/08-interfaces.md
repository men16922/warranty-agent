# L5 — 인터페이스 (포트/어댑터 · HTTP 계약)

`Satisfies: REQ-604, REQ-801, REQ-802`

---

## 1. 왜 포트/어댑터인가 — 취향이 아니라 REQ-801 때문이다

`make check`는 **네트워크 없이, 과금 없이** 돌아야 한다. 그런데 이 시스템은 Vertex·
Firestore·Cloud Monitoring·Cloud Run·BigQuery를 쓴다. **경계가 없으면 만족 불가능하다.**

⇒ **포트는 게이트의 전제 조건이다.**

| 포트 | 책임 | 실제 | 테스트 |
|---|---|---|---|
| `ModelPort` | 모델 호출 + 토큰 계량 | Vertex | `FakeModel` (고정 응답·고정 usage) |
| `SignalSource` | 신호 읽기 | Cloud Monitoring | `FakeSignal` (시계열을 스크립트로 준다) |
| `RunControl` | 리비전·트래픽 조작 | Cloud Run Admin | `FakeRun` (배분 상태를 들고 있다) |
| `ActionExecutor` | 조치 실행 | GCP SDK | `RecordingExecutor` (**호출 횟수를 센다**) |
| `ContractStore` / `LedgerStore` / `BudgetStore` | 상태 | Firestore | 인메모리 |
| `BillingSource` | 청구 행 | BigQuery | `FakeBilling` |
| `Clock` / `IdGen` | 시각·id | 시스템·ULID | `FrozenClock` / `SeededIdGen` |

⚠️ **`RecordingExecutor`의 호출 횟수가 G1의 전부다** — `DENY`/`MANUAL`일 때 그 수가 0이어야
한다. 판정만 확인하는 테스트는 *"판정은 했는데 실행은 됐다"*를 못 잡는다.

⚠️ **`FakeSignal`이 시계열을 스크립트로 주는 것이 검증 테스트의 핵심이다** — 회복·미회복·
애매·빈 창 네 가지를 **값으로 명시**해 태운다. 행복 경로만 태우면 가드가 하중을 안 받는다.

## 2. 저장소가 불변식을 집행한다

`LedgerStore`에 범용 `update()`가 **없다.** 범용 쓰기가 있으면 REQ-505(`assumed` 불변)가
*관례*가 되고, 관례는 언젠가 깨진다.

⚠️ **불변식을 문서가 아니라 API 모양으로 집행한다.**

## 3. HTTP 계약

| 메서드 | 경로 | 목적 | REQ |
|---|---|---|---|
| `POST` | `/resources:provision` | Day-1 — 생성 + **계약 방출** | 101–103 |
| `GET` | `/contracts/{id}` | 계약 조회 | 102 |
| `POST` | `/actions/{action_id}:remediate` | 게이트 → 조치 → **검증 → 롤백** | 401–403, 2xx, 3xx |
| `POST` | `/ledger/{entry_id}:approve` | 승인 후 재판정 | 404 |
| `GET` | `/ledger/{entry_id}` | 항목 1건 (근거 포함) | 604 |
| `GET` | `/report/daily?date=` | **회복률 리포트** | 508 |
| `POST` | `/agent:chat` | ADK 에이전트. **앱 bearer 인증 필수**(D15) | 601, 603 |
| `GET` | `/livez` | 플랫폼 프로브. ⛔ **`/healthz`가 아니다** — Cloud Run이 가로챈다 (2026-08-23 실물) | |

### 3.A 앱 인증 경계 — 공개 URL은 무인 과금 권한이 아니다

Cloud Run invoker는 `allUsers`로 둔다(D15). 심사위원이 Hosted URL과 `/livez`를 열 수 있어야
하기 때문이다. 대신 **과금이 시작되는 `/agent:chat`만** 다음 계약으로 막는다.

- 요청: `Authorization: Bearer <WR_AGENT_AUTH_TOKEN>`.
- 토큰 값: 저장소·`.env.example`·배포 argv에 넣지 않는다. Cloud Run의 `--set-secrets`가
  Secret Manager `warranty-agent-auth:latest`를 환경변수로 주입한다.
- 토큰 미설정·32바이트 미만: `503 auth_unavailable` — 보호 없이 시작하지 않는다.
- 헤더 누락·형식 오류·불일치: 전부 같은 `401 unauthorized` + `WWW-Authenticate: Bearer`.
- 비교: `hmac.compare_digest`; 오류 본문·로그에는 입력 토큰과 기대 토큰을 싣지 않는다.
- `/livez`와 미등록 경로는 인증과 무관하다. 프로브가 토큰을 요구하면 새 리비전이 뜰 수 없다.

⚠️ 지금 유효한 토큰을 내도 `/agent:chat`은 `501`이다. 인증은 **실물 에이전트 배선의 선행**이지,
없는 어댑터를 성공으로 가장하는 장치가 아니다.

### 3.1 `remediate` 응답 — ★ 이 한 덩어리가 논지다

```jsonc
{
  "entry_id": "01k2m9x7q3f4b8n0v6c1t5r2wz",
  "status": "executed",
  "decision": {
    "verdict": "AUTO",
    "reversibility": "reversible", "verifiable": true, "headroom_usd": "0.42",
    "rule": "reversible × verifiable × headroom"
  },
  "verification": {
    "verdict": "not_recovered",
    "decided_by": "model",
    "rationale": "Error rate improved 60% but p95 latency rose 2.3× above baseline;
                  the action traded one symptom for another.",
    "baseline": {"error_rate": 0.184}, "after": {"error_rate": 0.073, "p95_ms": 1840}
  },
  "rollback": {
    "performed": true,
    "verified_traffic": {"warranty-api-00007-abc": 100},
    "signal_restored": true
  },
  "executed": true, "improved": false, "rolled_back": true,   // ★ 셋이 따로 있다
  "assumed": {"amount_usd": "0.0021", "inputs": {...}, "unit_prices": {...}}
}
```

⚠️ **`rule`·`rationale`·`verified_traffic`이 응답에 있는 이유**: 4분 안에 전달되려면
**화면에 보여야** 한다(REQ-604). 로그에만 있으면 없는 것과 같다.

## 4. 오류 모델

| 상황 | HTTP | 비고 |
|---|---|---|
| 게이트 `DENY`/`MANUAL` | **`200`** | 오류가 아니라 **정상 판정**. 원장 항목이 생긴다 |
| 승인 대기 | `202` | |
| 계약 없음 | **`200`** | `status: manual_required` (REQ-104) |
| 미등록 조치 | `404` | |
| 계약 필드 누락 | `400` | 빠진 필드명 |
| `/agent:chat` 인증 누락·실패 | `401` | 토큰 값은 응답·로그에 없음 |
| `/agent:chat` 인증 비밀 미설정·취약 | `503` | fail-close; `/livez`는 계속 200 |

⚠️ `DENY`를 `403`으로 내면 클라이언트가 **재시도**하고, 재시도는 REQ-501을 시험한다.

## 5. 설정

`WR_PROJECT_ID` · `WR_REGION` · `WR_MODEL` · `WR_ADAPTERS`(live|fake) ·
`WR_BILLING_TABLE`(선택) · `WR_RECONCILE_DEADLINE_DAYS` · `WR_AGENT_AUTH_TOKEN`(Secret Manager 주입)

⚠️ **기본값을 fake로 두지 않는다** — 배포가 조용히 가짜로 돌 수 있다.
테스트가 **명시적으로** fake를 주입하고, 게이트 중 라이브 어댑터 생성이 없음을 G5가 확인한다.
