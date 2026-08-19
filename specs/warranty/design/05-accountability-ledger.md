# L4 — 책임 원장

`Satisfies: REQ-501, REQ-502, REQ-503, REQ-504, REQ-505, REQ-506, REQ-507, REQ-508, REQ-509`

---

## 1. 원장 행

```python
LedgerEntry:
    entry_id:     str          # 소문자 ULID 26자 — GCP 라벨 제약에서 유도된 형식
    agent_id:     str
    action_id:    str
    contract_id:  str | None   # 없으면 manual_required (REQ-104)
    status:       Status       # executed | denied | failed | awaiting_approval | manual_required
    started_at:   datetime

    decision:      Decision           # 없을 수 없다 (REQ-401)
    verification:  Verification | None  # 실행된 조치만 갖는다
    rollback:      Rollback | None
    attribution:   Attribution
    assumed:       CostFact           # 쓰인 뒤 불변 (REQ-505)
    measured:      CostFact | None    # (선택) 청구 화해
    delta:         Delta | None
    retry_of:      str | None
```

### ★ 1.1 셋을 따로 갖는다 (REQ-502)

```python
    @property executed:     bool   # 조치 API가 성공했는가
    @property improved:     bool   # 신호가 회복됐는가
    @property rolled_back:  bool   # 되돌렸는가
```

**`executed=true, improved=false, rolled_back=true`** 가 이 시스템이 말할 수 있고
대부분의 도구가 말할 수 없는 문장이다.

⚠️ **이 셋을 하나의 `success`로 합치는 순간 이 프로젝트의 논지가 사라진다.**
`improved`는 저장하지 않고 `verification.verdict`에서 **유도한다** — 저장하면 어긋날 수 있다.

## 2. 비용 사실 (REQ-503, REQ-505)

```python
CostFact:
    amount_usd: Decimal
    inputs:     Mapping[str, Decimal]   # 수량
    unit_prices: Mapping[str, Decimal]  # 단가 (inputs와 키가 같아야 한다)
    priced_at:  datetime
    basis:      published_rate | billing_export
```

⚠️ **총액만 남기면 어느 가정이 총액을 지배하는지 영원히 모른다.**
⚠️ **`assumed`는 실측이 와도 절대 덮지 않는다** — 덮으면 "우리 추정이 얼마나 틀렸나"를 못 본다.

**집행은 API 모양으로 한다**: 저장소에 범용 `update()`가 없다. 화해는 `reconcile()`만 할 수
있고 그것이 만질 수 있는 것은 `measured`·`delta`·`reconcile_state`뿐이다.
관례로 두면 언젠가 깨진다.

## 3. 귀속 (REQ-504)

| 방법 | 언제 | 검증 가능성 |
|---|---|---|
| `resource_label` | 라벨을 붙일 수 있는 리소스를 만졌다 | `reconcilable` |
| `token_meter` | 모델 호출 — 라벨 붙일 대상이 없다 | `assumed_only` |
| `none` | 과금 리소스 없음 또는 라벨 실패 **(사유 필수)** | `assumed_only` |

**방법 → 검증가능성 매핑은 코드에 한 벌만 있다.** 복사본 둘은 다음 고침이 한쪽에만 닿는다.

## 4. 청구 화해 *(선택 · REQ-506, REQ-509)*

라벨로 BigQuery 결제 내보내기 행을 맞춰 `measured`를 채우고 차이를 파생한다.
멱등이고, 기한 내 못 맞추면 사유와 함께 `unreconciled`.

⚠️ **크레딧을 분리해 읽는다** — 크레딧이 사용액을 상쇄해 기본 조회가 **$0으로 보인다.**
"안 썼다"와 "크레딧이 덮었다"는 다르고, 크레딧으로 도는 프로젝트에서 이 구분을 안 하면
**모든 실측이 0이 된다.**

⚠️ **선택 항목이다** — 내보내기가 하루 지연이라 크리티컬 패스에 두지 않는다.

## 5. ★ 일간 리포트 (REQ-508)

```jsonc
{
  "date": "2026-08-28", "agent_id": "warranty",
  "executed": 41,
  "improved": 23,
  "improvement_rate": 0.56,        // ★ 헤드라인
  "rolled_back": 12,
  "escalated": 6,
  "unverifiable": 3,               // 정직성 칸
  "manual_required": 4,
  "wasted_usd": "0.84",            // 회복 실패 조치가 쓴 비용
  "model_decided": 5               // 애매해서 모델이 판정한 건수 (REQ-204)
}
```

**`improvement_rate`가 이 시스템의 헤드라인이다.** 어떤 운영 에이전트도 이 숫자를 내지 않는다 —
다들 `executed`만 세고 그것을 성공이라 부른다.

⚠️ `unverifiable`을 리포트에 **드러내 놓는다.** 구조적으로 드러나는 한계는 감점이 아니라
신뢰의 근거다.
