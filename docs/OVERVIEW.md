# warranty — 개요

> ▶ **NEXT SESSION: 첫 행동 = 콘솔에서 크레딧이 붙은 결제 계정을 확인하고 전용 GCP 프로젝트를
> 만드는 것.** 그것 하나가 T2 전체를 잠그고 있다 — 계획은 `specs/warranty/tasks.md` **T0-3**.
> ⛔ **08-24까지 Cloud Run에서 도는 것이 없으면 접는다**(포기 비용 0).
> 열리면 T0-3 → **T2-1**(ADK 실물 호출 — 임포트만 확인됐다) → T2-2(배포) → T3(계약 방출).
> 배포 재료(`Dockerfile`·`deploy.sh`·`demo-target`)는 **있다 — 한 번도 실행된 적이 없다.**
> ⛔ **첫 배포는 실패한다**: 이미지가 HTTP를 안 내보내 포트 프로브에서 죽는다(서버는 T2-2).
> ⚠️ **오프라인 `[auto]` 백로그는 고갈됐다**(T11-5가 마지막). 남은 T11-6은 오늘 생긴 것이다.
> ⚠️ 남은 `[auto]`와 `.env`의 부트스트랩 `WR_PROJECT_ID`는
> [`tasks.md`](../specs/warranty/tasks.md)가 권위다 — **여기서 세지 않는다.**

> **인프라를 만든 에이전트가, 그것을 어떻게 고쳐야 하는지도 함께 적어 둔다.**
> 그리고 조치한 뒤 **실제로 나아졌는지 다시 재고**, 안 나아졌으면 **원자적으로 되돌린다.**
>
> Google All Things Agentic Hackathon · Fortified Enterprise Fleet 트랙
> 작성 2026-08-19 · 상태: **설계 완료 · 구현 진행 중**

사람이 읽는 진입점이다. 요구사항의 권위는
[`specs/warranty/requirements.md`](../specs/warranty/requirements.md),
결정 근거의 권위는 [`design.md`](../specs/warranty/design.md).
**이 문서는 그림과 서사를 소유한다.**

---

## 1. 문제

Remediation 에이전트는 조치를 실행하고 **성공을 보고한다.**
**실행 성공은 증상이 사라졌다는 뜻이 아니다.**

- 재시작했다 → 재시작은 성공했다 → **오류율은 그대로다**
- 스케일을 올렸다 → API가 200을 줬다 → **지연은 더 나빠졌다**
- 트래픽을 옮겼다 → 옮겨졌다 → **원인이 다른 곳이었다**

셋 다 **로그는 똑같이 초록이다.** 대부분의 도구는 그 차이를 말하지 못한다.

## 2. 왜 GCP 전용인가 — 이게 논지다

> **클라우드 중립성을 포기하면 에이전트가 무엇을 할 수 있게 되는가.**

중립적인 에이전트는 **모든 클라우드에서 표현 가능한 조치만** 할 수 있다.
그래서 실행하고 성공을 보고하지만 — 나아졌는지 증명하지 못하고, 원자적으로 되돌리지 못하고,
그 조치가 얼마 썼는지 말하지 못한다.

| 중립성이 막는 것 | GCP 올인이 여는 것 |
|---|---|
| 신호를 정규화하면 고유 정보가 깎인다 | **Cloud Monitoring을 그대로 읽는다** → 진짜 검증 |
| 되돌림이 점진적이면 자동 롤백을 못 믿는다 | **Cloud Run 트래픽 전환 = 원자적**, 배분으로 **증명** |
| 조치당 비용 귀속에 공통 수단이 없다 | **리소스 라벨이 결제 행에 실려 온다** |
| 자격증명이 전역이면 경계가 코드 필터다 | **테넌트별 SA + WIF** *(선택)* |

**대부분의 제출물은 멀티클라우드를 자랑으로 내건다. 이 프로젝트는 특화를 능력의 조건으로 내건다.**

## 3. 정책 한 줄

> ⛔ **검증할 수 없는 조치는 자동으로 실행하지 않는다.**
>
> 확인 못 하는 자동화는 자동화가 아니라 **방치**다.

## 4. 아키텍처

```mermaid
flowchart TB
    NL["Request<br/>(natural language or API)"] --> RUN

    subgraph RUN["Cloud Run · warranty-api  (scale-to-zero)"]
        AGENT["ADK Agent · Gemini 3.7 Flash"]
        PROV["provision<br/>creates resource"]
        CONTRACT["★ Operational Contract<br/>health signal · recovery criterion<br/>rollback plan · reversibility"]
        GATE["decision gate<br/>reversibility × <b>verifiability</b> × budget"]
        EXEC["execute"]
        VERIFY["★ verify<br/>re-measure the same signal"]
        RB["★ rollback<br/>traffic → previous revision"]
        LED["accountability ledger<br/>executed · improved · rolled_back"]

        AGENT -->|Day-1| PROV --> CONTRACT
        AGENT -->|Day-2| GATE
        CONTRACT -.->|"tells the gate what is verifiable"| GATE
        GATE -->|AUTO| EXEC
        GATE -.->|"DENY / MANUAL — executor never called"| LED
        EXEC --> VERIFY
        VERIFY -->|recovered| LED
        VERIFY -->|not recovered| RB --> LED
    end

    CONTRACT --> FS[("Firestore")]
    LED --> FS
    VERIFY <-->|read signal| CM[("Cloud Monitoring")]
    RB <-->|traffic split + verify| CR[("Cloud Run Admin")]

    style CONTRACT fill:#ddd6fe,stroke:#6d28d9,color:#000
    style GATE fill:#fde68a,stroke:#b45309,color:#000
    style VERIFY fill:#bfdbfe,stroke:#1d4ed8,color:#000
    style RB fill:#fecaca,stroke:#b91c1c,color:#000
```

## 5. 조치 하나의 일생

```mermaid
sequenceDiagram
    participant A as Agent
    participant G as Gate
    participant M as Cloud Monitoring
    participant R as Cloud Run
    participant L as Ledger

    A->>G: remediate(service, action)
    Note over G: reversible ✓ · verifiable ✓ · headroom ✓ → AUTO
    A->>M: baseline = read(contract.health_signal)
    A->>R: execute action
    Note over A: wait VERIFY_DELAY
    A->>M: after = read(<b>same</b> signal spec)
    Note over A: ★ ambiguous → model judges,<br/>rationale recorded
    A-->>L: verdict = not_recovered
    A->>R: traffic 100% → previous revision
    A->>R: <b>read traffic split back</b> — proof, not claim
    A->>M: re-measure → signal restored ✓
    A-->>L: executed=true · improved=false · rolled_back=true
```

**이 마지막 한 줄이 이 시스템이 말할 수 있고 대부분의 도구가 말할 수 없는 문장이다.**

## 6. 판정 게이트 — 축이 셋

```mermaid
flowchart TD
    S{"budget headroom?"} -->|no| DENY["DENY<br/>executor not called"]
    S -->|yes| V{"<b>verifiable?</b><br/>(contract exists,<br/>signal readable)"}
    V -->|no| RV{"reversible?"}
    V -->|yes| RV2{"reversible?"}
    RV -->|yes| APP1["APPROVE<br/>⛔ we don't automate<br/>what we can't verify"]
    RV -->|no| MAN["MANUAL"]
    RV2 -->|yes| AUTO["AUTO"]
    RV2 -->|no| APP2["APPROVE"]

    style AUTO fill:#bbf7d0,stroke:#15803d,color:#000
    style DENY fill:#fecaca,stroke:#b91c1c,color:#000
    style APP1 fill:#fde68a,stroke:#b45309,color:#000
    style MAN fill:#e5e7eb,stroke:#4b5563,color:#000
```

⚠️ **검증 가능성이 축이라는 것이 이 프로젝트의 주장이다.** 되돌릴 수 있어도 나아졌는지
확인할 수 없으면 자동으로 하지 않는다.

## 7. 헤드라인 숫자

```
executed          41
improved          23   ←  56%      ★ 어떤 운영 에이전트도 안 내는 숫자
rolled back       12
escalated          6
unverifiable       3   ←  정직성 칸
model decided      5   ←  애매해서 모델이 판정한 건수
wasted            $0.84 ←  회복 실패 조치가 쓴 비용
```

대부분의 도구는 **`executed`만 세고 그것을 성공이라 부른다.**

## 8. 기술 스택 (대회 필수 요건)

| 요건 | 충족 |
|---|---|
| Gemini 3.5 이상 | **Gemini 3.7 Flash** (Vertex AI) |
| Google Agent Framework | **ADK** |
| Google Cloud 인프라 | **Cloud Run** + Firestore + Cloud Monitoring (+ BigQuery, 선택) |

⛔ GKE·상시 VM·Cloud SQL 안 씀 — 유휴 과금 0으로 수렴.

## 9. 이 저장소는 spec-driven이다

```mermaid
flowchart LR
    R["requirements.md<br/>REQ-###"] -->|Satisfies| D["design/*.md"]
    R -->|Implements| T["tasks.md"]
    R -->|"Verifies:"| E["tests/"]
    E -->|"mutation red 확인"| M["evidence/mutations.md"]
    G(["G6 guard · make check"]) -.->|"상태 주장 ↔ 현실"| R
    G -.-> D
    G -.-> T
    G -.-> E
    G -.-> M
    style G fill:#fde68a,stroke:#b45309,color:#000
```

- 상태가 `IMPLEMENTED`면 → **테스트가 있어야 한다**
- 상태가 `VERIFIED`면 → **지워 보고 red를 확인한 변이 기록이 있어야 한다**
- 어긋나면 **`make check`가 red다**

## 10. 현재 상태

```
게이트    `make check` — 통과 수는 tasks.md 하단 한 곳에만 적는다
요구사항  44종 — 상태 분포는 `make trace`가 센다 (사람이 세어 적지 않는다)
가드      G1~G4 · G6~G9 변이 확인 · G5만 미착수 → tasks.md「가드 현황」
변이      선언한 것 전부 red 확인 · 복구 후 초록 · 잔여 0 → docs/evidence/mutations.md
루프      조치→검증→롤백 **전부 fake 위에서 배선·검증됨**. 남은 건 어댑터뿐
ADK       google-adk 2.7.1 인터페이스 실재 확인. ⛔ **모델 호출은 아직**
README    재현 절차가 게이트를 지난다(T11-5). ⛔ 그전엔 `make demo`가 절차에 **없었다**
```

⚠️ **여기에 숫자를 세어 적지 않는다**(T0-6의 교훈) — 실제로 썩어 있었다: 이 상자가 말하던
`120 passed`·`VERIFIED 18`·`M-01~M-32`·`커밋 6개`는 **넷 다 틀렸다.** ⇒ 세는 자리는 하나다.

**다음**: ⛔ **T2 — Cloud Run 배포.** [`tasks.md`](../specs/warranty/tasks.md)가 권위.
남은 TODO는 대부분 실물 GCP를 요구하고, 오프라인 `[auto]`를 다 해도
**중단 기준의 판정 대상(T2-2)은 움직이지 않는다.**

### 막혀 있는 것

| | 왜 | 잠그는 것 |
|---|---|---|
| **전용 GCP 프로젝트** | 크레딧이 붙은 결제 계정을 못 읽음 (Billing API 미활성) | 배포 전체 |
| BQ 결제 내보내기 *(선택)* | 콘솔 수동 · 하루 지연 | REQ-506·509만 |

### ⛔ 중단 기준

**08-24까지 Cloud Run에서 도는 것이 없으면 접는다.** 포기 비용 0.

## 11. 무엇을 하지 않는가

**멀티클라우드 어댑터** · 멀티테넌트 격리 티어 · 공급망/이미지 서명 · GitOps · 웹 대시보드 ·
런북 카탈로그 · 에스컬레이션 티어 · Model Armor.

⚠️ **멀티클라우드는 범위 밖이 아니라 논지의 반대편이다**(§2).

## 12. 알려진 한계 — 숨기지 않는다

- **인과가 아니라 상관이다.** 조치 후 회복이 조치 때문이라는 증명은 아니다.
  롤백 후 재측정이 **약한 자연 실험**을 제공하지만 인과는 세우지 못한다.
- **계약은 프로비저닝을 거친 리소스만 갖는다.** 손으로 만든 리소스는 자동 대상이 아니다 —
  **버그가 아니라 정책**이다.
- **회복률은 "우리 기준으로" 회복률이다.** 계약의 판정 기준이 틀리면 검증도 틀린다.
- **공유 리소스의 비용 귀속은 못 푼다.** 한 조치 = 한 리소스인 경우에만 라벨 귀속을 쓴다.

## 13. 용어

| 용어 | 뜻 |
|---|---|
| **운영 계약** | Day-1이 산출하는, 그 리소스를 어떻게 검증·롤백하는지의 선언 |
| **verifiable** | 계약이 살아 있고 신호를 지금 읽을 수 있는가. **판정 게이트의 축** |
| **improved** | 조치 후 신호가 계약 기준으로 회복됐는가. **`executed`와 다른 값** |
| **assumed / measured** | 계산한 비용 / 청구서가 말한 비용. **전자는 절대 안 덮는다** |
| **가역성** | 되돌릴 수 있는가. 승인 게이트의 축(severity가 아니다) |
