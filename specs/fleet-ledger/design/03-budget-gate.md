# L4 — 예산 게이트

`Satisfies: REQ-301, REQ-302, REQ-303, REQ-304, REQ-305, REQ-306, REQ-307`

---

## 1. 게이트가 하는 일과 안 하는 일

**한다**: 실행 **전에** 예상 비용과 남은 여유를 비교해 **실행을 막는다.**
**안 한다**: 경보. 알림. 사후 보고.

⚠️ **"경보가 아니라 거부"가 이 컴포넌트의 전부다.** 경보만 내는 예산 도구는 이미 GCP에
있고(Budgets API), 그것이 실지출을 못 읽는다는 것이 이 프로젝트의 출발점이다.

## 2. 판정 행렬 (REQ-302)

```
                   projected ≤ headroom      projected > headroom
                 ┌────────────────────────┬────────────────────────┐
   reversible    │        ALLOW           │         DENY           │
                 ├────────────────────────┼────────────────────────┤
   irreversible  │   REQUIRE_APPROVAL     │         DENY           │
                 └────────────────────────┴────────────────────────┘
```

### 왜 축이 가역성인가
`severity`는 "얼마나 급한가"를 말한다. 사람이 개입해야 하는 진짜 이유는 급해서가 아니라
**틀렸을 때 되돌릴 수 없어서**다. 급하지만 되돌릴 수 있는 조치는 자동으로 해도 되고,
급하지 않지만 되돌릴 수 없는 조치는 사람이 봐야 한다.

### 왜 가역인데도 초과면 DENY인가
가역 액션은 **내일 다시 하면 된다.** 거부 비용이 낮다. 반면 예산을 넘겨 실행하면
그 초과분은 되돌릴 수 없다 — **돈은 언제나 비가역이다.**

### 왜 비가역인데 여유가 있으면 APPROVE인가
예산이 남았다는 것은 **돈 문제가 없다**는 뜻이지 **해도 된다**는 뜻이 아니다.
비가역성은 예산과 독립한 위험이다.

## 3. 예약 프로토콜 (REQ-305)

```
   reserve(budget_id, projected)          ── Firestore 트랜잭션
     headroom = limit - committed - reserved
     if projected > headroom:  return DENY
     reserved += projected
     return ALLOW, reservation_id

   ── 액션 실행 ──

   settle(budget_id, reservation_id, assumed)   ── Firestore 트랜잭션
     reserved  -= projected
     committed += assumed
```

**동시 요청 2건**(한도 $1.00, 각 projected $0.60): 첫 트랜잭션이 `reserved=0.60`을 커밋하면
두 번째는 headroom $0.40을 보고 `DENY`. **둘 다 통과하는 경로가 없다.**

⚠️ **`settle`이 안 돌면 예산이 조용히 잠긴다.** 실행이 예외로 끝나도 `settle`이 도는
경로를 둔다. 그리고 **`unsettled_reservations`를 지표로 낸다** — 조용히 잠긴 예산은
"예산이 없다"와 구분이 안 되고, 구분 안 되는 실패가 가장 오래 산다.

## 4. `projected`는 어디서 오나

레지스트리의 `cost_model`이 계산한다. 액션마다 다르다:

```python
cost_model.project(params) -> CostFact   # basis = published_rate
```

`projected`는 **`CostFact`다** — 총액만이 아니라 **수량 가정과 단가를 함께** 갖는다.
그래야 나중에 "게이트가 왜 틀렸나"를 총액이 아니라 **어느 가정이 틀렸는지**로 답할 수 있다.

⚠️ 레퍼런스의 100배 오차는 **정가가 아니라 수량 가정**에서 왔다. 총액만 남기는 게이트는
자기가 왜 틀렸는지 영원히 모른다.

## 5. ★ 게이트 자신의 오차 (REQ-307)

이 프로젝트의 가장 날카로운 주장이다.

> **게이트는 추정으로 판정한다. 그런데 이 프로젝트의 출발점은 "추정은 100배 틀린다"는
> 실측이다. 그러므로 게이트를 신뢰하려면 게이트의 오차율을 알아야 한다.**

화해가 끝난 항목에 대해:

```
   projection_error(entry) = measured.amount_usd / budget_decision.projected_usd
```

일간 리포트에 `gate_projection_error = {mean_ratio, p95_ratio, n, worst_entry_id}`를 낸다.

**이것이 데모의 결정적 장면이다:**
> *"게이트는 이 액션을 $0.02로 예측하고 허용했습니다. 청구서는 $1.90이었습니다.
> 이 게이트의 p95 오차는 47배입니다. — 그래서 우리는 게이트를 믿지 않고, 측정합니다."*

⚠️ **자기 도구의 오차를 산출물로 내는 것**이 Innovation 40%에 대한 우리의 대답이다.
대부분의 도구는 자기 정확도를 안 잰다.

## 6. 승인 경로 (REQ-304)

범위 최소화: **API 호출**로 승인한다(사람 UI 없음 — 요구사항 §10 Q3).

```
   POST /ledger/{entry_id}:approve   {"by": "<principal>"}
     → status: awaiting_approval → (재판정) → executed
```

⚠️ **승인 시점에 게이트를 다시 판정한다.** 승인 대기 중에 예산이 소진됐을 수 있다.
승인은 "비가역성에 대한 동의"지 "예산 면제"가 아니다.

## 7. 게이트가 조용히 깨지는 방식 (그래서 가드가 있다)

| 깨짐 | 증상 | 가드 |
|---|---|---|
| 판정은 하는데 실행을 안 막음 | 로그가 똑같아 보인다 | **G1** — `DENY` 시 실행기 호출 횟수 0 |
| 게이트를 안 거친 실행 경로 | 항목에 `budget_decision` 없음 | **G4** — 모든 항목에 존재 |
| 행복 경로만 태운 테스트 | 초과 분기가 도달 불가 | 판정 4칸을 **값으로 명시** |
| `settle` 누락 | 예산이 잠김 | `unsettled_reservations` 지표 + 테스트 |

⚠️ **G1은 지워 보고 red를 확인한 뒤에만 가드로 인정한다**(`07-verification.md`).
