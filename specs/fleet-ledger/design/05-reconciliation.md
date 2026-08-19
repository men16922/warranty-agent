# L4 — 화해 (BigQuery 결제 내보내기)

`Satisfies: REQ-401, REQ-402, REQ-403, REQ-404, REQ-405, REQ-406, REQ-204`

---

## 1. 왜 BigQuery뿐인가 — 측정된 사실

Cloud Billing API의 discovery 문서를 전수한 결과:

- 메서드 **19개** 중 지출(사용량·실제 비용)을 읽는 것 **0개**
- `services.skus.list`는 **가격표**(rate card)지 사용량이 아니다
- Budgets API의 `Budget.amount`는 **내가 설정한 금액**이다. 실지출 readout이 없다
- 결제 내보내기 토글은 **콘솔 수동**이고 API로 못 켠다

⇒ **실지출을 읽는 경로는 BigQuery 결제 내보내기 하나뿐이고, 하루 지연된다.**

⚠️ **이것이 이 프로젝트가 2단계 원장을 갖는 이유 전체다.** 아키텍처가 도메인의 진실에서
유도됐지 취향에서 나오지 않았다.

## 2. 선행 조건 (일정의 하한)

```
   콘솔에서 결제 내보내기 활성화  ──▶  최초 데이터 도착까지 최대 ~24–48h
                                       │
                                       └──▶ REQ-4xx 전체가 여기 뒤에 있다
```

⚠️ **08-19에 안 켜면 화해를 실증할 수 없다.** 이것은 코드로 우회 불가하다.
`tasks.md` T0-3이 이 항목이고, **가장 먼저 해야 하는 수동 작업**이다.

## 3. 매칭 알고리즘 (REQ-401)

```sql
-- 개념. 실제 컬럼명은 표준 사용량 내보내기 스키마 확인 후 확정한다(T5-1)
SELECT
  label.value            AS entry_id,
  SUM(cost)              AS cost_usd,
  SUM((SELECT SUM(c.amount) FROM UNNEST(credits) c)) AS credit_usd,
  COUNT(*)               AS billing_rows
FROM `<project>.<dataset>.gcp_billing_export_v1_<ACCOUNT_ID>`,
     UNNEST(labels) AS label
WHERE label.key = 'fl_entry'
  AND usage_start_time >= @window_start      -- ⚠️ 파티션 필터 필수 (§6)
  AND usage_start_time <  @window_end
GROUP BY entry_id
```

### ⚠️ 크레딧을 빼지 않으면 $0으로 보인다
레퍼런스 저장소의 실측 함정: **크레딧이 사용액을 상쇄해 기본 조회가 $0을 반환한다.**
`cost`만 보면 "안 썼다"로 읽히는데 실제로는 쓰고 크레딧이 덮은 것이다.

⇒ **`cost`와 `credits`를 둘 다 읽고, `measured`에 둘 다 남긴다.**
`measured.inputs = {"cost": ..., "credits": ...}`, `amount_usd = cost` (크레딧 전).

**"크레딧 덕에 안 냈다"와 "안 썼다"는 다르다.** 해커톤 크레딧으로 도는 이 프로젝트에서
이 구분은 **장식이 아니라 필수**다 — 안 그러면 우리 데모의 모든 `measured`가 0이 된다.

## 4. 멱등 (REQ-403)

```
   for entry_id, agg in query_results:
       entry = load(entry_id)
       if entry.reconcile_state == reconciled:  continue      # ← 멱등의 전부
       entry.measured  = CostFact(..., basis=billing_export)
       entry.delta     = delta_of(entry.assumed, entry.measured)
       entry.reconcile_state = reconciled
       store.put(entry)                                        # assumed는 안 건드림 (I-1)
```

⚠️ **`reconciled_at`도 갱신하지 않는다.** 재실행이 타임스탬프만 바꾸면 "언제 화해됐나"가
거짓이 되고, 멱등성 테스트가 통과하면서도 의미가 새는 전형적인 방식이다.

## 5. 미화해 처리 (REQ-404)

```
   if entry.reconcile_state == pending
      and now - entry.finished_at > RECONCILE_DEADLINE_DAYS:
          entry.reconcile_state = unreconciled
          entry.reconcile_note  = "no billing row matched label fl_entry=<id> within Nd"
```

`RECONCILE_DEADLINE_DAYS` 기본 **3**. 근거: 내보내기 지연이 보통 하루, 최대 이틀 관측.
⚠️ 이 값은 **관측에서 온 가정이지 보증이 아니다.** 상수 한 곳에 두고 이름을 붙인다(REQ-704).

**왜 조용히 비워 두지 않나**: 빈 `measured`는 *"아직 안 왔다"*와 *"영원히 안 온다"*를
구분하지 못한다. 구분 안 되는 상태가 가장 오래 산다.

## 6. ★ 화해기 자신의 비용 (REQ-406)

BigQuery는 **스캔한 바이트로 과금**한다. 화해 조회 자체가 지출이다.

```
   job.total_bytes_billed × BQ_ON_DEMAND_PRICE_PER_TIB
        └──▶ LedgerEntry(agent_id="fleet-ledger", action_id="reconcile",
                         method=token_meter형이 아닌 metered, verifiability=assumed_only)
```

⚠️ **측정 자체가 과금이다.** 레퍼런스 저장소에서 비용 점검 API 호출(건당 $0.01)이
**그날의 최대 지출 항목**이었던 날이 실제로 있다. **장부가 장부값보다 비싸면 그 장부는
틀린 도구이고, 그 사실은 장부 안에서만 보인다.**

**비용 가드**: ① 파티션 필터 필수(없으면 전체 스캔) ② 일 1회 실행 ③ 필요한 컬럼만 SELECT.

## 7. 실행 형태

**Cloud Run Job + Cloud Scheduler**(일 1회). API 프로세스 안에서 폴링하지 않는다 —
그러면 scale-to-zero가 깨지고 REQ-705를 어긴다.

데모에서는 `POST /reconcile`로 **수동 트리거**한다(REQ-703의 결정론을 위해).
⚠️ 수동 트리거 경로와 스케줄 경로는 **같은 함수를 부른다.** 두 경로가 갈라지면 데모에서
검증된 것이 운영 경로가 아니게 된다.
