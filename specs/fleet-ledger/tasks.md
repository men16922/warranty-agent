# tasks — fleet-ledger

작성: 2026-08-19 · 권위: `requirements.md` · 설계: `design.md` + `design/*.md`

> **모든 태스크는 REQ와 설계 절을 가리킨다.** 가리키는 것이 없는 태스크는 범위 밖이다.
> 완료 표기는 `[x]`, 진행 중은 `[~]`. **`[x]`는 테스트가 있고 변이로 red를 확인한 것만.**

---

## 일정 제약 (이것이 순서를 결정한다)

```
   08-19 (오늘) ──── 08-21 ──── 08-24 ──────── 08-28 ──── 08-31
        │              │          │              │          │
        T0            T2      ★ 중단 기준      크레딧      제출
     스캐폴딩    Cloud Run에    "Cloud Run에    마감      09-01 09:00 KST
     + BQ 켜기    hello 배포     도는 게 없으면
                                 버린다"
```

⚠️ **T0-3(BQ 결제 내보내기)이 오늘의 최우선이다.** 활성화 후 데이터 도착까지 하루 이상
걸리고, **REQ-4xx 전체가 그 뒤에 있다.** 코드로 우회 불가하다.

---

## T0 — 기반 (08-19, 오늘)

- [ ] **T0-1** 레포 스캐폴딩: `pyproject.toml`, `Makefile`(check 타깃), `src/fleet_ledger/`, `tests/`
      · `Implements: REQ-701, REQ-702` · `Design: 07-verification §1`
- [ ] **T0-2** overnight-harness 설치 + **permission boundary에 배포/과금 명령 deny**
      · `Design: docs/COST_GUARDRAILS.md`
- [ ] **T0-3** ⛔ **BQ 결제 내보내기 활성화 (콘솔 수동 · 사용자 작업)**
      · `Implements: REQ-401` · `Design: 05-reconciliation §2`
- [ ] **T0-4** 전용 GCP 프로젝트 생성 + 크레딧 붙은 결제 계정 연결
      · `Implements: REQ-705` · `Design: 08-deployment §1`
- [ ] **T0-5** G6(추적성 가드) 먼저 만든다 — **spec을 지키게 만드는 장치를 첫날 세운다**
      · `Implements: 추적성 규약` · `Design: 07-verification §3.1`

⚠️ **T0-5를 뒤로 미루면 SDD가 장식이 된다.** 가드가 없는 동안 쓰인 코드는 spec을 안 지켜도
아무 일이 일어나지 않고, 나중에 붙이면 그때 전부 red가 되어 결국 가드를 끈다.

## T1 — 도메인 (08-19~20, 전부 오프라인)

- [ ] **T1-1** `LedgerEntry`·`CostFact`·`Attribution`·`Delta` 자료형 + 검증
      · `Implements: REQ-202, REQ-203` · `Design: 01-domain-model §2`
- [ ] **T1-2** `LedgerStore` 포트 + `InMemoryLedger` + **I-1 집행**(범용 update 없음)
      · `Implements: REQ-204` · `Design: 06-interfaces §3` · **가드 G2**
- [ ] **T1-3** `method ↔ verifiability` 매핑을 **한 벌만** 두고 집행
      · `Implements: REQ-203` · `Design: 01-domain-model §2.2` · **가드 G3**
- [ ] **T1-4** 상태 기계 + 전이 규칙 (`retry_of` 포함)
      · `Implements: REQ-201, REQ-207` · `Design: 01-domain-model §3` · **가드 G7**
- [ ] **T1-5** `Clock`·`IdGen` 포트 + ULID 소문자 26자 (라벨 제약 검사 포함)
      · `Implements: REQ-702, REQ-205` · `Design: 02-attribution §2`

## T2 — ★ 배포 선행 (08-20~21) — **중단 기준의 판정 대상**

- [ ] **T2-1** ADK **실물 설치**하고 최소 에이전트가 로컬에서 응답
      · `Implements: REQ-501` · `Design: 04-agent-runtime §2`
- [ ] **T2-2** 컨테이너 + Artifact Registry + **Cloud Run 배포**
      · `Implements: REQ-502` · `Design: 08-deployment §2`
- [ ] **T2-3** 실제 왕복 증거 남기기 (`docs/evidence/live-roundtrip-<date>.log`)
      · `Implements: REQ-501, REQ-801` · `Design: 07-verification §6`

⚠️ **T2-1의 수용 기준은 "테스트 통과"가 아니라 "실제 라이브러리로 실제 응답"이다.**
스텁 위에서 통과하는 테스트는 이 REQ를 만족시키지 못한다(`07-verification §6`).

⛔ **08-24까지 T2-2가 안 되면 프로젝트를 접는다.** 포기 비용은 0이다.

## T3 — 레지스트리 + 게이트 (08-22~23)

- [ ] **T3-1** `AgentAction` + 적재 시 3필드 필수 검증 (기본값 없음)
      · `Implements: REQ-101, REQ-102, REQ-103` · `Design: 01-domain-model §4`
- [ ] **T3-2** 판정 행렬 4칸을 **값으로 명시**해 태운다
      · `Implements: REQ-302` · `Design: 03-budget-gate §2`
- [ ] **T3-3** ★ `DENY`가 실행기를 **안 부른다** (`RecordingExecutor.call_count == 0`)
      · `Implements: REQ-303` · `Design: 03-budget-gate §7` · **가드 G1**
- [ ] **T3-4** 예약/정산 트랜잭션 + `unsettled_reservations` 지표
      · `Implements: REQ-305, REQ-306` · `Design: 03-budget-gate §3` + `01-domain-model §5`
- [ ] **T3-5** 모든 항목에 `budget_decision` 존재
      · `Implements: REQ-301` · `Design: design.md §5 I-4` · **가드 G4**
- [ ] **T3-6** 승인 경로 + **승인 시 재판정**
      · `Implements: REQ-304` · `Design: 03-budget-gate §6`

## T4 — 귀속 (08-23~25)

- [ ] **T4-1** `ActionExecutor`가 생성 리소스에 `fl_entry` 라벨 부착
      · `Implements: REQ-205` · `Design: 02-attribution §2`
- [ ] **T4-2** 라벨 실패 시 `none` + 사유, **실행은 계속**
      · `Implements: REQ-206` · `Design: 02-attribution §2`
- [ ] **T4-3** `ModelPort`가 호출마다 `token_meter` 항목 기록
      · `Implements: REQ-503` · `Design: 04-agent-runtime §4`
- [ ] **T4-4** 단가 상수 모듈 + `priced_at`
      · `Implements: REQ-202` · `Design: 04-agent-runtime §4`

## T5 — 화해 (08-25~27) — **T0-3 데이터 도착 후에만 가능**

- [ ] **T5-1** 결제 내보내기 **실제 스키마 확인** 후 질의 확정 (⚠️ 컬럼명 추측 금지)
      · `Implements: REQ-401` · `Design: 05-reconciliation §3`
- [ ] **T5-2** **크레딧 분리 판독** — `cost`와 `credits` 둘 다 기록
      · `Implements: REQ-402` · `Design: 05-reconciliation §3`
- [ ] **T5-3** `measured`·`delta` 채우기 + **`assumed` 불변 확인**
      · `Implements: REQ-402, REQ-204` · **가드 G2**
- [ ] **T5-4** 멱등 (재실행이 `reconciled_at`도 안 바꾼다)
      · `Implements: REQ-403` · `Design: 05-reconciliation §4`
- [ ] **T5-5** 기한 초과 → `unreconciled` + 사유
      · `Implements: REQ-404` · `Design: 05-reconciliation §5`
- [ ] **T5-6** 토큰 일간 집계 화해 (행 상태는 안 바꾼다)
      · `Implements: REQ-405` · `Design: 02-attribution §3`
- [ ] **T5-7** ★ 화해기가 자기 BQ 스캔 비용을 원장에 적는다
      · `Implements: REQ-406` · `Design: 05-reconciliation §6`
- [ ] **T5-8** Cloud Run Job + Scheduler (수동 트리거와 **같은 함수**)
      · `Implements: REQ-401` · `Design: 05-reconciliation §7`

## T6 — 출력 (08-27~28)

- [ ] **T6-1** 실행 응답에 판정 근거(`rule` 포함) + `executed` 필드
      · `Implements: REQ-601` · `Design: 06-interfaces §4.1`
- [ ] **T6-2** 일간 리포트 (총계 · 상태별 분포)
      · `Implements: REQ-602` · `Design: 06-interfaces §4.2`
- [ ] **T6-3** ★ 게이트 예측 오차 집계
      · `Implements: REQ-307, REQ-603` · `Design: 03-budget-gate §5`

## T7 — 데모 (08-28~29)

- [ ] **T7-1** `make demo` — 결정론적 5단계
      · `Implements: REQ-703` · `Design: 09-demo §2`
- [ ] **T7-2** 데모 상수 한 모듈
      · `Implements: REQ-704` · `Design: 09-demo §5`
- [ ] **T7-3** ⚠️ **데모 전날 실제 액션 실행** — 당일 화해에 진짜 청구 데이터가 있게
      · `Design: 09-demo §1` 원칙 5
- [ ] **T7-4** G5 (게이트 중 라이브 어댑터 생성 0) 변이 확인
      · `Implements: REQ-701` · **가드 G5**

## T8 — 제출 (08-30~31)

- [ ] **T8-1** 아키텍처 다이어그램 · `Implements: REQ-801`
- [ ] **T8-2** README — 재현 가능한 실행/배포 절차 · `Implements: REQ-801`
- [ ] **T8-3** ★ **4분 영어 영상** (구성은 `09-demo §3`) · `Implements: REQ-801`
- [ ] **T8-4** 클린룸 확인 — 의존성·소스에 레퍼런스 저장소 유래 없음 · `Implements: REQ-802`
- [ ] **T8-5** Devpost 제출 (마감 **09-01 09:00 KST**)
- [ ] **T8-6** teardown 날짜 캘린더 등록 (**09-02**) · `Design: 08-deployment §6`

---

## 가드 완료 현황 (변이로 red를 확인한 것만 `[x]`)

| 가드 | 태스크 | 상태 |
|---|---|---|
| G1 `DENY` 집행 | T3-3 | [ ] |
| G2 `assumed` 불변 | T1-2, T5-3 | [ ] |
| G3 method↔verifiability | T1-3 | [ ] |
| G4 모든 항목에 판정 | T3-5 | [ ] |
| G5 게이트 오프라인 | T7-4 | [ ] |
| G6 ★ 추적성 | T0-5 | [ ] |
| G7 1회=1행 | T1-4 | [ ] |
