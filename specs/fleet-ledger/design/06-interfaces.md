# L5 — 인터페이스 (포트/어댑터 · HTTP 계약)

`Satisfies: REQ-601, REQ-602, REQ-603, REQ-701, REQ-702`

---

## 1. 왜 포트/어댑터인가 — 취향이 아니라 REQ-701 때문이다

`make check`는 **네트워크 없이, 과금 없이** 돌아야 한다(REQ-701). 그런데 이 시스템은
Vertex·Firestore·BigQuery를 쓴다. **경계가 없으면 이 요구사항은 만족 불가능하다.**

레퍼런스 저장소가 정확히 여기서 넘어졌다 — 게이트가 **테스트마다 모델을 과금 호출**하고
있었고, 고치자 **288초 → 39초**가 됐다. **깨진 테스트는 0건**이었다. 즉 아무도 몰랐다.

⇒ **포트는 설계 취향이 아니라 게이트의 전제 조건이다.**

## 2. 포트 목록

| 포트 | 책임 | 실제 어댑터 | 테스트 어댑터 |
|---|---|---|---|
| `ModelPort` | 모델 호출 + **토큰 계량**(REQ-503) | Vertex AI | `FakeModel` (고정 응답·고정 usage) |
| `LedgerStore` | 원장 읽기/쓰기 + **I-1 집행** | Firestore | `InMemoryLedger` |
| `RegistryStore` | 액션 정의 | Firestore | `InMemoryRegistry` |
| `BudgetStore` | 예약/정산 트랜잭션 | Firestore | `InMemoryBudget` |
| `BillingSource` | 청구 행 질의 | BigQuery | `FakeBilling` (고정 행) |
| `ActionExecutor` | 실제 GCP 작업 + **라벨 부착** | GCP SDK | `RecordingExecutor` (호출 횟수를 센다) |
| `Clock` | `now()` | 시스템 | `FrozenClock` |
| `IdGen` | `new_entry_id()` | ULID | `SeededIdGen` |

⚠️ **`RecordingExecutor`가 호출 횟수를 세는 것이 G1의 전부다** — `DENY`일 때 그 수가 0이어야
한다. 판정만 확인하는 테스트는 "판정은 했는데 실행은 됐다"를 못 잡는다.

⚠️ **`Clock`과 `IdGen`이 포트인 이유는 REQ-702(결정론)다.** 레퍼런스에서 픽스처가 절대
시각을 하드코딩하고 생산자가 살아 있는 시계를 쓴 탓에, **통과가 달력이 움직이기 전까지만
참**이었던 사건이 있다.

## 3. `LedgerStore`가 불변식을 집행한다

```python
class LedgerStore(Protocol):
    def create(self, entry: LedgerEntry) -> None: ...
    def get(self, entry_id: str) -> LedgerEntry | None: ...
    def reconcile(self, entry_id: str, measured: CostFact) -> LedgerEntry: ...
    def query(self, agent_id: str, date: date) -> list[LedgerEntry]: ...
```

**`update(entry)` 같은 범용 쓰기 메서드를 두지 않는다.**
범용 쓰기가 있으면 I-1(`assumed` 불변)이 **관례**가 되고, 관례는 언젠가 깨진다.
`reconcile()`은 `measured`·`delta`·`reconcile_state`만 만질 수 있고, 구현이 그것을 강제한다.

⚠️ **불변식을 문서가 아니라 타입/API 모양으로 집행한다.** 이것이 이 인터페이스 설계의 요지다.

## 4. HTTP 계약

| 메서드 | 경로 | 목적 | REQ |
|---|---|---|---|
| `POST` | `/actions/{action_id}:execute` | 게이트 → 실행 → 원장 | 301, 303, 201 |
| `POST` | `/ledger/{entry_id}:approve` | 승인 후 재판정 | 304 |
| `GET` | `/ledger/{entry_id}` | 항목 1건 (판정 근거 포함) | 601 |
| `GET` | `/ledger?agent=&date=` | 항목 목록 | 602 |
| `GET` | `/report/daily?agent=&date=` | 총계 + **게이트 오차** | 602, 603 |
| `POST` | `/reconcile` | 화해 수동 트리거 (Job과 같은 함수) | 401, 403 |
| `POST` | `/agent:chat` | ADK 에이전트 대화 | 501, 503 |
| `GET` | `/healthz` | | |

### 4.1 `POST /actions/{id}:execute` 응답 — ★ 판정 근거가 응답에 있다

```jsonc
{
  "entry_id": "01k2m9x7q3f4b8n0v6c1t5r2wz",
  "status": "denied",
  "budget_decision": {
    "verdict": "DENY",
    "budget_id": "fleet-steward:2026-08-26",
    "projected_usd": "5.0000",
    "headroom_before_usd": "0.1000",
    "reversibility": "reversible",
    "rule": "projected > headroom"          // 어느 칸에서 나온 판정인지
  },
  "attribution": { "method": "none", "reason": "action not executed" },
  "assumed":  { "amount_usd": "0.0000", "inputs": {}, "unit_prices": {} },
  "verifiability": "assumed_only",
  "executed": false                          // ⚠️ 이 필드가 REQ-303의 관측 지점이다
}
```

⚠️ **`rule` 필드를 넣는 이유**: 판정 행렬 네 칸 중 어디서 나왔는지가 안 보이면,
데모에서 *"왜 막혔죠?"*에 답할 수 없다. 로그가 아니라 **응답**에 있어야 한다(REQ-601).

### 4.2 `GET /report/daily` 응답

```jsonc
{
  "agent_id": "fleet-steward", "date": "2026-08-26",
  "entries": 41,
  "assumed_total_usd":  "0.8412",
  "measured_total_usd": "3.9107",
  "unreconciled_total_usd": "0.1200",
  "by_verifiability": { "reconcilable": 28, "assumed_only": 13 },
  "by_reconcile_state": { "reconciled": 24, "pending": 4, "unreconciled": 1, "not_applicable": 12 },
  "gate_projection_error": {                    // ★ REQ-307
    "n": 24, "mean_ratio": "4.65", "p95_ratio": "47.10",
    "worst_entry_id": "01k2m9x7q3f4b8n0v6c1t5r2wz"
  },
  "token_aggregate": {                          // REQ-405
    "assumed_total_usd": "0.0391", "sku_total_usd": "0.0402", "ratio": "1.03"
  }
}
```

**이 한 응답이 4분 영상의 마지막 장면이다.** 여기 있는 모든 숫자가 논지의 한 조각이다.

## 5. 오류 모델

| 상황 | HTTP | 본문 |
|---|---|---|
| 미등록 액션 (REQ-103) | `404` | `{"error":"action_not_registered","action_id":...}` |
| 게이트 DENY (REQ-303) | **`200`** | 위 응답, `status:"denied"` |
| 승인 대기 (REQ-304) | **`202`** | `status:"awaiting_approval"` |
| 레지스트리 정의 불완전 (REQ-102) | `400` | 빠진 필드명 |
| 실행 실패 | `200` | `status:"failed"` + 원장 항목 |

⚠️ **DENY를 `403`으로 내지 않는 이유**: 거부는 오류가 아니라 **정상적인 판정 결과**이고,
원장 항목이 만들어진다. 오류로 내면 클라이언트가 재시도하게 되고, 재시도는 I-5를 시험한다.

## 6. 설정 (환경변수)

| 변수 | 기본 | 비고 |
|---|---|---|
| `FL_PROJECT_ID` | — | 필수 |
| `FL_MODEL` | `gemini-3.5-flash` | |
| `FL_BILLING_TABLE` | — | 화해에 필수 |
| `FL_RECONCILE_DEADLINE_DAYS` | `3` | REQ-404 |
| `FL_ADAPTERS` | `live` | **`fake`면 전부 테스트 어댑터** |

⚠️ **`FL_ADAPTERS=fake`가 기본이 아니다.** 기본을 fake로 두면 배포가 조용히 가짜로 돌 수
있다. 대신 **테스트가 명시적으로 fake를 주입**하고, G5가 게이트 중 라이브 어댑터 생성이
없음을 확인한다.
