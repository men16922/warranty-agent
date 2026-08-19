# requirements — fleet-ledger

작성: 2026-08-19 · **L1 · 이 문서가 가장 높은 권위다**

> 표기: EARS(Easy Approach to Requirements Syntax).
> `Ubiquitous` 시스템은 항상 ~한다 · `Event` ~할 때, 시스템은 ~한다 ·
> `State` ~인 동안 · `Unwanted` 만약 ~라면, 시스템은 ~한다 · `Optional` ~인 경우.
>
> ⚠️ **수용 기준이 없는 요구사항은 요구사항이 아니다.** 각 REQ는 Given/When/Then을 갖는다.

---

## 0. 논지 (요구사항이 아니라 요구사항의 이유)

대부분의 agent observability는 **토큰·지연·오류**를 본다. **에이전트가 만든 클라우드 지출**은
안 본다. 그리고 그 지출의 *추정*은 **안심시키는 쪽으로 체계적으로 틀린다** — 레퍼런스
저장소의 실측에서 "수백 시계열" 가정이 실제 **52,438**이었고 월 비용 추정이 **약 100배**
틀렸다(`docs/REFERENCE_FROM_PARENT.md` #1).

⇒ **fleet-ledger는 에이전트의 행동 하나하나에 지출을 귀속하고, 자신의 추정이 얼마나
틀렸는지를 스스로 드러내는 장부다.**

---

## 1. 레지스트리 (REQ-1xx)

### REQ-101 — 액션은 등록된 것만 실행된다
`Ubiquitous` 시스템은 에이전트와 각 에이전트가 수행할 수 있는 액션의 레지스트리를 유지한다.

- **Given** 레지스트리에 `restart_service`가 등록되어 있고
- **When** 그 액션의 실행이 요청되면
- **Then** 시스템은 실행 경로로 진입한다.

상태: `TODO`

### REQ-102 — 등록은 세 가지를 반드시 선언한다
`Ubiquitous` 등록된 각 액션은 (a) 비용 모델, (b) **가역성 등급**, (c) **귀속 방법**을 선언한다.

- **Given** 세 필드 중 하나라도 없는 액션 정의가 주어지고
- **When** 레지스트리가 그것을 적재하면
- **Then** 시스템은 적재를 거부하고 어느 필드가 빠졌는지 보고한다.

⚠️ **기본값을 주지 않는다.** 조용한 기본값은 선언을 무의미하게 만든다
(`REFERENCE_FROM_PARENT.md` #4).

상태: `TODO`

### REQ-103 — 미등록 액션은 거부된다
`Unwanted` 만약 요청된 액션이 레지스트리에 없다면, 시스템은 그것을 실행하지 않고 거부 사유를 기록한다.

- **Given** 레지스트리에 없는 액션 id가 주어지고
- **When** 실행이 요청되면
- **Then** 아무 부수효과 없이 거부되고, **원장에 거부 항목이 남는다**(REQ-207).

상태: `TODO`

---

## 2. 원장 (REQ-2xx)

### REQ-201 — 액션 1회 = 원장 1행
`Event` 액션이 실행될 때, 시스템은 정확히 하나의 원장 항목을 쓴다.

- **Given** 게이트를 통과한 액션이 있고
- **When** 실행이 끝나면(성공이든 실패든)
- **Then** `entry_id`가 유일한 원장 항목 1개가 존재한다. 재시도는 새 항목을 만들지 않는다.

상태: `TODO`

### REQ-202 — `assumed`는 측정 수량과 함께 기록된다
`Ubiquitous` 원장 항목은 **측정된 사용량 × 공시 단가**로 계산한 `assumed` 비용을,
**그 계산에 쓰인 수량과 단가와 가격 기준 시각과 함께** 기록한다.

- **Given** 60초 동안 실행된 액션이 있고
- **When** 원장 항목이 쓰이면
- **Then** `assumed.amount_usd`뿐 아니라 `assumed.inputs`(수량), `assumed.unit_prices`,
  `assumed.priced_at`이 모두 존재한다.

⚠️ **총액만 적으면 어느 가정이 총액을 지배하는지 알 수 없다.** 레퍼런스에서 정확히 이것이
100배 오차의 원인이었다 — 정가는 맞았고 **수량 가정**이 틀렸다(#1·#2).

상태: `TODO`

### REQ-203 — 검증 가능성을 행마다 표시한다
`Ubiquitous` 원장 항목은 `verifiability`를 `reconcilable` 또는 `assumed_only` 중 하나로 표시한다.

- **Given** 라벨을 붙일 수 있는 리소스를 만든 액션
- **Then** `verifiability == "reconcilable"`.
- **Given** 모델 호출(토큰 계량)만 한 액션
- **Then** `verifiability == "assumed_only"`이고 `reason`이 채워진다.

⚠️ **이 프로젝트는 검증할 수 없는 행을 숨기지 않는다.** 어느 칸이 측정이고 어느 칸이
가정인지 표시하는 것이 논지의 절반이다(#2).

상태: `TODO`

### REQ-204 — `assumed`는 절대 덮어쓰지 않는다
`Ubiquitous` 시스템은 `measured`가 도착해도 `assumed`를 수정하거나 삭제하지 않는다.

- **Given** `assumed.amount_usd = 0.02`인 항목
- **When** 화해가 `measured.amount_usd = 1.90`을 채우면
- **Then** `assumed.amount_usd`는 여전히 `0.02`이고 `delta`가 파생된다.

⚠️ **이것이 이 시스템의 최상위 불변식이다.** 추정을 실측으로 덮으면 "추정이 얼마나 틀렸나"를
영원히 못 본다 — 그게 이 프로젝트의 존재 이유다.

상태: `TODO`

### REQ-205 — 과금 리소스에는 원장 id 라벨을 박는다
`Event` 액션이 과금되는 GCP 리소스를 만들거나 변경할 때, 시스템은 그 리소스에
원장 항목 id를 담은 라벨을 붙인다.

- **Given** 라벨을 지원하는 리소스를 만드는 액션
- **When** 리소스가 생성되면
- **Then** 라벨 `fl_entry=<entry_id>`가 리소스에 존재하고, entry_id는 GCP 라벨 제약
  (소문자·숫자·`-`·`_`, ≤63자)을 만족한다.

상태: `TODO`

### REQ-206 — 라벨을 못 붙이면 그 사실을 적는다
`Unwanted` 만약 대상 리소스가 라벨을 지원하지 않거나 라벨 부착이 실패하면, 시스템은
항목을 `assumed_only`로 표시하고 **사유를 기록한 뒤** 실행을 계속한다.

- **Then** 항목에 `attribution.method == "none"`과 `attribution.reason`이 남는다.
- **그리고** 실행 자체는 막지 않는다 — 장부가 못 세는 것과 액션이 못 도는 것은 다른 문제다.

상태: `TODO`

### REQ-207 — 거부와 실패도 원장에 남는다
`Ubiquitous` 시스템은 실행된 액션뿐 아니라 **게이트가 거부한 액션과 실행에 실패한 액션**도
원장에 기록한다.

- **Then** `status ∈ {executed, denied, failed, awaiting_approval}`이고, `denied` 항목의
  `assumed.amount_usd == 0`이며 `budget_decision.verdict == "DENY"`가 남는다.

⚠️ **거부를 기록하지 않으면 "게이트가 얼마를 막았는가"를 못 답한다** — 그게 게이트의 유일한 실적 지표다.

상태: `TODO`

---

## 3. 예산 게이트 (REQ-3xx)

### REQ-301 — 실행 전에 판정하고, 판정을 원장에 남긴다
`Event` 액션이 실행되기 전에, 시스템은 예산 게이트를 평가하고 그 판정을 원장 항목에 기록한다.

- **Then** 항목에 `budget_decision.{verdict, budget_id, projected_usd, headroom_before_usd}`가 존재한다.

상태: `TODO`

### REQ-302 — 판정 축은 **가역성 × 예산 여유**다
`Ubiquitous` 게이트는 액션의 **가역성**과 **남은 예산 여유** 두 축으로 판정한다.

| | `projected ≤ headroom` | `projected > headroom` |
|---|---|---|
| **가역(reversible)** | `ALLOW` | `DENY` |
| **비가역(irreversible)** | `REQUIRE_APPROVAL` | `DENY` |

⚠️ **축은 severity가 아니다.** 심각도는 "얼마나 급한가"를 말할 뿐 "틀렸을 때 되돌릴 수
있는가"를 말하지 않는다 — 승인이 필요한 진짜 이유는 후자다(#8).

상태: `TODO`

### REQ-303 — `DENY`는 경보가 아니라 집행이다
`Unwanted` 만약 게이트가 `DENY`를 반환하면, 액션은 **실행되지 않는다**.

- **Given** headroom $0.10, projected $5.00인 가역 액션
- **When** 실행이 요청되면
- **Then** 액션 실행기가 **호출되지 않는다**(호출 횟수 0), 원장에 `status="denied"`가 남는다.

⚠️ **이 REQ가 이 프로젝트에서 가장 쉽게 조용히 깨지는 것이다.** 판정만 적고 실행을 막지
않아도 로그는 똑같아 보인다. G1이 이것을 변이로 지킨다.

상태: `TODO`

### REQ-304 — `REQUIRE_APPROVAL`은 기록된 승인 없이는 진행하지 않는다
`State` 항목이 `awaiting_approval`인 동안, 시스템은 그 액션을 실행하지 않는다.

- **When** 명시적 승인이 기록되면 **Then** 실행되고 항목의 `approval.{by, at}`이 남는다.

상태: `TODO`

### REQ-305 — 예약으로 동시 초과를 막는다
`Event` 게이트가 `ALLOW`할 때, 시스템은 `projected` 금액을 예산에 **예약**하고, 실행이 끝나면
예약을 실제 `assumed` 금액으로 대체한다.

- **Given** 한도 $1.00, 동시에 도착한 projected $0.60짜리 액션 2건
- **Then** 하나는 `ALLOW`, 다른 하나는 `DENY`다. 둘 다 통과하지 않는다.

상태: `TODO`

### REQ-306 — 예산은 에이전트별·일별로 범위를 갖는다
`Ubiquitous` 예산은 `(agent_id, date)` 범위로 정의되고, 게이트는 그 범위의 한도만 본다.

상태: `TODO`

### REQ-307 — ★ 게이트 자신의 예측 오차를 측정한다
`Ubiquitous` 시스템은 게이트가 사용한 `projected` 금액과 화해된 `measured` 금액의 차이를
**게이트의 예측 오차로 집계**한다.

- **Given** 화해가 끝난 항목들
- **When** 일간 리포트를 요청하면
- **Then** `gate_projection_error.{mean_ratio, p95_ratio, n}`이 반환된다.

⚠️ **이것이 이 프로젝트의 가장 날카로운 주장이다.** 예산 게이트는 *추정*으로 판정하는데,
이 프로젝트의 출발점은 **추정이 100배 틀린다**는 실측이다. 그러므로 **게이트를 신뢰하려면
게이트의 오차율을 알아야 한다.** 우리는 그것을 측정해서 낸다.

상태: `TODO`

---

## 4. 화해 (REQ-4xx)

### REQ-401 — 라벨로 청구 행을 원장에 맞춘다
`Event` 화해가 실행될 때, 시스템은 BigQuery 결제 내보내기를 읽어 `fl_entry` 라벨 값으로
청구 행을 원장 항목에 대응시킨다.

상태: `TODO`

### REQ-402 — `measured`와 `delta`
`Event` 대응하는 청구 행을 찾았을 때, 시스템은 `measured`를 채우고 `delta`를 파생한다.

- **Then** `delta.amount_usd == measured - assumed`, `delta.ratio == measured / assumed`
  (`assumed == 0`이면 `ratio`는 `null`이고 `delta.note`가 사유를 적는다).

상태: `TODO`

### REQ-403 — 화해는 멱등이다
`Ubiquitous` 같은 창(window)에 대해 화해를 여러 번 실행해도 결과는 같다.

- **Given** 이미 화해된 항목 **When** 같은 창으로 다시 실행하면 **Then** 값이 변하지 않고
  `reconciled_at`도 갱신되지 않는다.

상태: `TODO`

### REQ-404 — 안 맞으면 안 맞았다고 적는다
`Unwanted` 만약 `RECONCILE_DEADLINE_DAYS` 안에 대응하는 청구 행이 없으면, 시스템은 항목을
`unreconciled`로 표시하고 사유를 기록한다.

⚠️ **조용히 비워 두지 않는다.** 빈 `measured`는 "아직 안 왔다"와 "영원히 안 온다"를 구분하지 못한다.

상태: `TODO`

### REQ-405 — 토큰 계량 항목은 **일간 총계로** 화해한다
`Ubiquitous` `assumed_only` 항목(모델 토큰)은 행 단위로는 검증할 수 없으므로, 시스템은
같은 날의 Vertex AI SKU 청구 총액과 **그 날의 토큰 추정 총액**을 대조해 집계 수준의
오차를 기록한다.

- **Then** 일간 리포트에 `token_aggregate.{assumed_total, sku_total, ratio}`가 존재한다.

⚠️ 행 단위 `verifiability`는 여전히 `assumed_only`다(REQ-203). **집계로 검증됐다고 해서
행이 검증된 것이 아니다** — 그 구분을 지우지 않는다.

상태: `TODO`

### REQ-406 — ★ 화해기는 자기 비용도 장부에 적는다
`Event` 화해가 실행될 때, 시스템은 그 BigQuery 조회가 스캔한 바이트에 대한 비용을
**자신의 원장 항목으로** 기록한다.

⚠️ **측정 자체가 과금이다.** 레퍼런스 저장소에서 비용 점검(CE 요청당 $0.01)이 **그날의
최대 지출 항목**이었던 날이 있다(#7). 장부가 장부값보다 비싸면 그 장부는 틀린 도구다 —
그리고 그 사실은 **장부 안에서만 보인다.**

상태: `TODO`

---

## 5. 에이전트 런타임 (REQ-5xx)

### REQ-501 — ADK + Gemini 3.5 이상 (대회 필수)
`Ubiquitous` 에이전트는 Google ADK로 구현되고 Vertex AI를 통해 Gemini 3.5 이상을 호출한다.

- **검증**: 배포된 서비스가 실제 응답을 반환하고, 그 응답의 usage 메타데이터가 원장에 기록된다.

⚠️ **스텁 위에서 통과하는 테스트는 이 REQ를 만족시키지 않는다.** 레퍼런스 저장소에서
정확히 이 실패가 있었다 — 테스트가 SDK를 스텁해 통과했는데 그 클래스는 **실제 라이브러리에
없었다**(#3-b). 이 REQ의 수용 기준은 **실물 호출**이다.

상태: `TODO`

### REQ-502 — Cloud Run에서 돈다 (대회 필수)
`Ubiquitous` API는 Cloud Run에서 실행되고, 유휴 시 인스턴스 0으로 수렴한다.

상태: `TODO`

### REQ-503 — ★ 모델 호출 자체가 원장 항목이 된다
`Event` 에이전트가 모델을 호출할 때, 시스템은 그 호출에 대한 원장 항목을
`attribution.method == "token_meter"`, `verifiability == "assumed_only"`로 기록한다.

- **Then** `assumed.inputs`에 `{input_tokens, output_tokens, model}`이 담긴다.

⚠️ **에이전트는 자기 자신도 함대의 일원이다.** 자기 비용을 안 세는 장부는 논지를 배반한다.

상태: `TODO`

---

## 6. 출력 (REQ-6xx)

### REQ-601 — 판정 근거는 로그가 아니라 출력이다
`Ubiquitous` 시스템은 각 원장 항목의 판정 근거(projected·headroom·verdict·귀속 방법)를
API 응답에 포함한다.

⚠️ **4분 영상 안에서 전달되려면 화면에 보여야 한다.** 내부 상태가 로그에만 있으면 없는 것과 같다.

상태: `TODO`

### REQ-602 — 일간 리포트
`Event` 특정 에이전트와 날짜에 대해 리포트가 요청되면, 시스템은
`assumed_total` · `measured_total` · `unreconciled_total` · 항목 수를 반환한다.

상태: `TODO`

### REQ-603 — 리포트는 게이트 오차를 포함한다
`Ubiquitous` 일간 리포트는 REQ-307의 게이트 예측 오차를 포함한다.

상태: `TODO`

---

## 7. 비기능 (REQ-7xx)

### REQ-701 — ★ 게이트(`make check`)는 오프라인이고 과금하지 않는다
`Ubiquitous` `make check`는 네트워크 접근 없이, **어떤 과금 API도 호출하지 않고** 완료된다.

- **Given** 네트워크가 차단된 환경
- **When** `make check`를 실행하면
- **Then** 통과한다. 모델·Firestore·BigQuery는 전부 fake 어댑터로 대체된다.

⚠️ **레퍼런스 저장소가 정확히 여기서 넘어졌다** — 게이트가 **테스트마다 Gemini를 과금
호출**하고 있었고, 고치자 288초 → 39초가 됐다(#3). **이 프로젝트도 Gemini를 쓴다. 같은
함정에 정확히 다시 들어간다.** G5가 이것을 변이로 지킨다.

상태: `TODO`

### REQ-702 — 게이트는 결정론적이다
`Ubiquitous` `make check`는 실제 시계·난수·외부 상태에 의존하지 않는다. 시각과 id는 주입된다.

상태: `TODO`

### REQ-703 — `make demo`는 결정론적으로 서사를 재현한다
`Event` `make demo`가 실행되면, 시스템은 **거부 → 실행 → 화해 → 오차 노출**의 전체 서사를
매번 같은 결과로 재현한다.

상태: `TODO`

### REQ-704 — 데모용 시간 상수는 한 곳에 있다
`Ubiquitous` 데모에 쓰이는 대기·창 길이는 **한 모듈의 명명된 상수**로 정의된다.

⚠️ 영상 길이에 맞춰 타이머를 줄이는 것은 최적화지만, **결과를 하드코딩하면 실증이 아니다**(#9).

상태: `TODO`

### REQ-705 — 상시 과금 컴퓨트를 만들지 않는다
`Ubiquitous` 배포 산출물은 유휴 시 0으로 수렴한다. **GKE·상시 VM은 쓰지 않는다.**

⚠️ 근거는 성질이 아니라 전례다 — 방치된 클러스터와 정지된 인스턴스가 실제로 청구됐다
(`docs/COST_GUARDRAILS.md`).

상태: `TODO`

---

## 8. 제출 (REQ-8xx)

### REQ-801 — 제출물 일체
`Ubiquitous` 제출은 코드 저장소 URL · **≤4분 영어 데모 영상** · 아키텍처 다이어그램 ·
재현 가능한 실행/배포 절차 · **Google Cloud 실행의 시각 증거**를 포함한다.

상태: `TODO`

### REQ-802 — 신규 프로젝트 · 편입 없음
`Ubiquitous` 이 프로젝트의 코드는 제출 기간(2026-08-03~08-31) 중 새로 작성되며,
레퍼런스 저장소(`platform-agent`)의 **코드를 임포트하거나 복사하지 않는다.**

- **검증**: 의존성 목록에 레퍼런스 저장소가 없고, 소스에 그 저장소 유래 코드가 없다.

⚠️ 대회 규칙의 신고 의무는 *"incorporated"* — **편입된 것**에 붙는다. 편입이 없으면
신고할 것이 없다. 상세는 `docs/REFERENCE_FROM_PARENT.md` §0.

상태: `TODO`

---

## 9. 범위 밖 (의도적으로 안 만드는 것)

멀티테넌트 격리 · blast radius 경계 · 이미지 서명/공급망 · 3-cloud 어댑터 · GitOps 렌더 ·
웹 대시보드 · Step Functions류 오케스트레이션 · 런북 스토어.

**이유**: 전부 레퍼런스 저장소를 크게 만든 것들이고 **4분 영상에서 하나도 안 보인다.**
심사 기준 어디에도 "규모"는 없다(`docs/HACKATHON.md`).

## 10. 미해결 질문

- **Q1** — GCP 프로젝트를 새로 만들 것인가? (권고: **그렇다.** 청구 귀속이 깨끗해지고
  teardown이 프로젝트 삭제 하나로 끝난다 → `design/08-deployment.md`)
- **Q2** — BQ 결제 내보내기가 켜지는 시각. **하루 지연**이 있으므로 이것이 REQ-4xx 전체의
  일정 하한이다. **오늘(08-19) 켜야 한다.**
- **Q3** — 승인(REQ-304) 경로를 사람 UI로 낼 것인가, API 호출로 둘 것인가. (권고: **API**,
  범위 최소화)
