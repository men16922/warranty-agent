# L4 — 운영 계약 (Day-1이 Day-2에 넘기는 것)

`Satisfies: REQ-101, REQ-102, REQ-103, REQ-104, REQ-105`

> **이 문서가 Day-1과 Day-2를 하나의 아이디어로 잇는다.** 계약이 없으면 이 프로젝트는
> 프로비저닝 도구와 운영 도구 **둘**이지, 하나가 아니다.

---

## 1. 문제

프로비저닝과 운영은 **다른 사람이 다른 시점에** 쓴다. 인프라를 만든 사람은 이 서비스가
건강한지 어떻게 아는지 알았고, 되돌리는 법도 알았다. **그 지식은 코드에 안 남는다.**
그래서 Day-2 에이전트는 그것을 **다시 알아내야** 하고, 대개 **추측한다.**

**추측한 신호로 하는 검증은 검증이 아니고, 추측한 롤백 계획은 필요할 때 틀린다.**

## 2. 계약의 모양

```python
OperationalContract:
    contract_id:        str
    resource:           ResourceRef        # 어떤 GCP 리소스인가 (타입·이름·리전)
    health_signal:      SignalSpec         # ① 무엇을 재면 건강한지 아는가
    recovery_criterion: Criterion          # ② 무엇을 회복이라 부르는가
    rollback_plan:      RollbackPlan       # ③ 어떻게 되돌리는가
    reversibility:      Reversibility      # ④ 되돌릴 수 있는가
    cost_model:         CostModelRef | None  # (선택)
    state:              ContractState      # active | retired
    provisioned_at:     datetime
    provisioned_by:     str                # 어떤 원장 항목이 이걸 만들었나
```

**①~④는 기본값이 없다**(REQ-102). 없으면 적재가 거부된다.
⚠️ 조용한 기본값은 선언을 장식으로 만들고, **그 장식 위에서 자동 조치가 돈다.**

### 2.1 `SignalSpec` — 무엇을 재는가
```python
SignalSpec:
    kind:            "cloud_monitoring"
    metric_type:     str    # 예: run.googleapis.com/request_count
    resource_filter: str    # 실제 만들어진 리소스 이름에서 유도된다 (REQ-103)
    aggregation:     str
    window_s:        int
```
⚠️ **기준선과 재측정은 이 스펙 하나를 공유한다**(REQ-202). 두 곳에 두면 다른 걸 재게 된다.

### 2.2 `Criterion` — 무엇을 회복이라 부르는가
```python
Criterion:
    direction: "decrease" | "increase"
    threshold: Decimal
    mode:      "relative" | "absolute"
    tolerance: Decimal        # 이 안쪽은 '애매'로 분류된다 → REQ-204
```
⚠️ **`tolerance`가 모델의 판단이 하중을 받는 자리를 만든다.** 이 값이 없으면 판정이 전부
이분법이 되고, 그러면 LLM은 파서일 뿐이다.

### 2.3 `RollbackPlan` — 어떻게 되돌리는가
```python
RollbackPlan:
    kind:              "cloud_run_traffic"   # 지금은 이것 하나
    previous_revision: str                   # 배포 직전에 확보된다
    verify_traffic:    bool = True           # 전환 후 실제 배분을 다시 읽는다 (REQ-303)
```

## 3. ★ 계약은 선언이 아니라 산출이다 (REQ-103)

**손으로 적는 계약은 낡는다.** 리소스는 바뀌는데 문서는 안 바뀐다.

| 필드 | 어디서 오나 |
|---|---|
| `resource` | 생성 API의 **응답** (실제 이름·리전) |
| `health_signal.resource_filter` | 그 이름 |
| `rollback_plan.previous_revision` | 배포 **직전의** 현재 리비전 |
| `reversibility` | 리소스 타입에서 유도 (Cloud Run 서비스 = 가역) |

**사람이 정하는 것은 `recovery_criterion` 하나뿐이다** — "무엇을 회복이라 부를지"는
**정책이지 사실이 아니기** 때문이다.

## 4. 계약이 없으면 (REQ-104)

**자동 조치를 하지 않는다.** 판정은 `MANUAL`, 원장에 사유가 남는다.

⚠️ 이것이 정책 *"검증할 수 없는 조치는 자동으로 하지 않는다"*의 집행 지점 중 하나다.
계약이 없다는 것은 **무엇을 재야 회복인지 모른다**는 뜻이고, 모르면 검증이 불가능하다.

## 5. 수명 (REQ-105)

리소스가 삭제되면 계약은 `retired`.
⚠️ **없는 리소스를 가리키는 계약이 살아 있으면, 자동 조치가 존재하지 않는 것을 고치려 한다.**
그 실패는 조용하다 — 조치는 "성공"하고 신호는 안 움직인다.

## 6. 알려진 한계

- **계약은 프로비저닝을 거친 리소스만 갖는다.** 손으로 만든 리소스는 자동 조치 대상이 아니다.
  ⚠️ **버그가 아니라 정책이다** — 그리고 영상에서 말한다.
- **`recovery_criterion`이 틀리면 검증도 틀린다.** 계약은 검증을 *가능하게* 하지 *옳게*
  만들지 않는다. 그래서 회복률(REQ-508)은 **"우리 기준으로"** 회복률이다.
