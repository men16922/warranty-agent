# L3 — 도메인 모델 · 불변식

`Satisfies: REQ-201, REQ-202, REQ-203, REQ-204, REQ-206, REQ-207, REQ-102, REQ-306`

---

## 1. 집합체(aggregate) 셋

| 집합체 | 컬렉션 | 수명 | 왜 분리했나 |
|---|---|---|---|
| `AgentAction` (레지스트리) | `registry_actions` | 배포와 함께 | 선언이지 사건이 아니다 |
| `Budget` | `budgets` | 하루 | 경합 지점이라 원장과 분리해야 예약이 안전하다 |
| `LedgerEntry` | `ledger_entries` | 영구 | **불변 기록.** 삭제하지 않는다 |

## 2. `LedgerEntry` — 원장 행

이 프로젝트에서 **유일하게 중요한 자료구조**다.

```python
LedgerEntry:
    entry_id:      str        # ULID 소문자 26자. GCP 라벨 제약을 만족한다(REQ-205)
    agent_id:      str
    action_id:     str
    status:        Status     # executed | denied | failed | awaiting_approval
    started_at:    datetime   # UTC. 주입된 Clock에서 온다(REQ-702)
    finished_at:   datetime | None

    budget_decision: BudgetDecision      # 없을 수 없다 (I-4)
    attribution:     Attribution         # 없을 수 없다 (I-3)
    assumed:         CostFact            # 쓰인 뒤 불변 (I-1)
    measured:        CostFact | None     # 화해가 채운다
    delta:           Delta | None        # 파생. 저장하되 계산식은 한 곳
    verifiability:   Verifiability       # reconcilable | assumed_only
    reconcile_state: ReconcileState      # pending | reconciled | unreconciled | not_applicable
    approval:        Approval | None     # REQ-304
```

### 2.1 `CostFact` — ★ 총액만 적지 않는다

```python
CostFact:
    amount_usd:  Decimal
    inputs:      dict[str, Decimal]   # 수량. 예: {"cpu_seconds": 60, "input_tokens": 1830}
    unit_prices: dict[str, Decimal]   # 단가. inputs와 키가 일치해야 한다
    priced_at:   datetime             # 이 단가를 언제 기준으로 읽었나
    basis:       Basis                # published_rate | billing_export
    source_note: str
```

⚠️ **`inputs`와 `unit_prices`의 키 집합이 다르면 유효하지 않은 `CostFact`다.**
총액만 남기면 **어느 가정이 총액을 지배하는지 영원히 모른다** — 레퍼런스에서 100배 오차의
원인이 정확히 이것이었다. 정가는 맞았고 수량 가정이 틀렸는데, 표에는 총액만 있었다.

**불변식 I-1**: `assumed`는 최초 기록 이후 어떤 경로로도 수정되지 않는다.
구현은 저장소 계층에서 막는다(수정 시도는 예외). 관례로 두지 않는다.

### 2.2 `Attribution` — 어떻게 청구서에 닿는가

```python
Attribution:
    method:      Method   # resource_label | token_meter | none
    label_key:   str | None      # "fl_entry"
    label_value: str | None      # == entry_id
    reason:      str | None      # method == none 일 때 필수 (REQ-206)
```

**method → verifiability 매핑은 강제된다(I-3):**

| `method` | `verifiability` | `reconcile_state` 초기값 |
|---|---|---|
| `resource_label` | `reconcilable` | `pending` |
| `token_meter` | `assumed_only` | `not_applicable` (행 단위로는) |
| `none` | `assumed_only` | `not_applicable` |

⚠️ **이 표가 코드에 한 벌만 존재해야 한다.** 두 곳에 복사하면 다음 고침이 한쪽에만 닿는다.

### 2.3 `Delta` — 파생값이지만 저장한다

```python
Delta:
    amount_usd: Decimal          # measured - assumed
    ratio:      Decimal | None   # measured / assumed. assumed==0이면 None
    note:       str | None       # ratio가 None인 사유
```

저장하는 이유는 질의 때문이다(일간 집계에서 매번 재계산하면 읽기 비용이 는다).
**계산식은 한 곳(`delta_of(assumed, measured)`)에만 두고, 저장은 그 함수의 출력만 받는다.**

## 3. 상태 기계

```
                      ┌──────────────────┐
   요청 ──▶ 게이트 ──▶ │ DENY             │──▶ denied  ────────────┐
              │        └──────────────────┘                        │
              │        ┌──────────────────┐                        │
              ├──────▶ │ REQUIRE_APPROVAL │──▶ awaiting_approval   │
              │        └────────┬─────────┘         │              │
              │                 │ 승인 기록          │              │
              │                 ▼                   │              │
              │        ┌──────────────────┐         │              │
              └──────▶ │ ALLOW            │◀────────┘              │
                       └────────┬─────────┘                        │
                                │ 실행                              │
                     ┌──────────┴──────────┐                       │
                     ▼                     ▼                       │
                 executed                failed                    │
                     │                     │                       │
                     └──────────┬──────────┘                       │
                                ▼                                  ▼
                        reconcile_state: pending ──────────▶  기록 종료
                                │                          (assumed=0, delta 없음)
                     ┌──────────┴──────────┐
                     ▼                     ▼
                reconciled            unreconciled
              (measured 있음)      (기한 초과, 사유 있음)
```

**전이 규칙**
- `denied`·`awaiting_approval` 항목도 **원장에 존재한다**(REQ-207). 이들의 `assumed.amount_usd == 0`.
- `failed`도 비용이 0이 아닐 수 있다 — **실패한 액션도 리소스를 만들었을 수 있다.**
  그래서 `failed`도 `reconcile_state: pending`으로 간다. ⚠️ 실패를 비용 0으로 가정하지 않는다.
- 종료 상태에서 되돌아가는 전이는 없다. 재시도는 **새 `entry_id`**를 만들고
  `retry_of` 필드로 원래 항목을 가리킨다(I-5를 깨지 않는 방법).

## 4. `AgentAction` — 레지스트리 항목

```python
AgentAction:
    action_id:     str
    agent_id:      str
    reversibility: Reversibility        # reversible | irreversible   (기본값 없음)
    cost_model:    CostModelRef         # projected 계산기 (기본값 없음)
    attribution:   Method               # 이 액션이 쓸 귀속 방법 (기본값 없음)
    description:   str
```

⚠️ **세 필드 모두 기본값이 없다**(REQ-102). 적재 시 없으면 **거부**한다.
조용한 기본값은 선언을 장식으로 만든다 — 레퍼런스에서 반복해 값을 치른 실패다.

## 5. `Budget` — 경합하는 유일한 집합체

```python
Budget:
    budget_id:    str        # f"{agent_id}:{date}"
    limit_usd:    Decimal
    committed_usd: Decimal   # 실행이 끝난 항목들의 assumed 합
    reserved_usd:  Decimal   # ALLOW되어 실행 중인 것들의 projected 합
    updated_at:   datetime
```

`headroom = limit - committed - reserved` (REQ-305).

**동시성**: `reserve → execute → settle`을 Firestore 트랜잭션으로 묶는다.
`settle`은 `reserved -= projected; committed += assumed`를 **한 트랜잭션에서** 한다.

⚠️ **`settle`을 빠뜨리면 예약이 영원히 남아 예산이 조용히 잠긴다.** 실행이 예외로 끝나도
`settle`이 도는 경로(finally)를 반드시 갖는다. `unsettled_reservations` 지표로 노출한다.

## 6. 화폐

- 모두 `Decimal`. **`float`를 쓰지 않는다.**
- 통화는 USD 하나. 다통화는 범위 밖(요구사항 §9).
- 직렬화는 문자열(`"0.0213"`). Firestore의 double 왕복이 값을 바꾸는 것을 막는다.
