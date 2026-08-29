# 대회 사실관계 — Google All Things Agentic Hackathon

원문 확인: 2026-08-15 (Official Rules) · 이 문서 작성: 2026-08-19
**요구사항의 권위는 `specs/warranty/requirements.md`다.** 이 문서는 **대회 쪽 사실**과
그 사실에 대한 **우리의 대응 매핑**만 담는다. 논지·서사의 권위는 `docs/OVERVIEW.md`다.

---

## 0. 이 프로젝트가 이 대회에서 하는 것

> ⚠️ 여기는 **매핑**이다. 논지 원문은 [`requirements.md` §0](../specs/warranty/requirements.md),
> 그림과 서사는 [`OVERVIEW.md`](OVERVIEW.md)가 소유한다. 여기서 다시 정의하지 않는다.

### 목적 — 한 문장

> **클라우드 중립성을 포기하면 에이전트가 무엇을 할 수 있게 되는가.**

중립적인 운영 에이전트는 **모든 클라우드에서 표현 가능한 조치만** 한다. 그래서 실행하고
성공을 보고하지만 셋을 못 한다. GCP 전용을 택하면 그 셋이 열린다 — **이 프로젝트는 그
셋이 실제로 열리는지 보이려고 존재한다.**

| # | GCP 전용이 사는 것 | 요구사항 | 심사 항목 | 트랙 요소 |
|---|---|---|---|---|
| ① | **검증** — 나아졌는지 같은 신호로 다시 잰다 | REQ-2xx | Innovation 40% | Agent Observability |
| ② | **원자적 롤백** — 되돌렸다고 주장하지 않고 배분을 되읽어 증명한다 | REQ-3xx | Innovation 40% | Agent Observability |
| ③ | **조치당 비용** — 라벨이 결제 행에 실려 오고, **추정과 실측을 안 섞는다** | REQ-503·504·505 | Innovation 40% | Agent Observability |

그리고 셋을 잇는 것이 **운영 계약**(REQ-1xx)이다 — 인프라를 만든 에이전트가 그것을 어떻게
검증·롤백하는지도 함께 적어 둔다. 판정 게이트(REQ-4xx)가 그 계약을 읽어 **검증할 수 없는
조치를 자동 실행에서 뺀다.** 그것이 이 프로젝트의 정책 한 줄이다.

### ⛔ 2026-08-29에 확인한 것 — 셋 중 하나는 지금 비어 있다

프로덕션 Firestore 원장의 **모든 조치 항목**을 읽었다:

```
action_id demo-target-00002-lss   status executed
  assumed.amount_usd  0
  attribution.method  none  ("no billable resource created")
```

⛔ **`executed`·`manual_required`·`awaiting_approval` 네 행 전부 `amount_usd = 0` ·
`attribution.method = none`이다.** ③의 기계는 다 있고(`CostFact`·`Attribution`·
`Basis`·예약/정산) 전부 `VERIFIED`인데, **실물 조치가 낸 비용 사실은 한 건도 없다.**
모델 호출 쪽도 마찬가지다 — `runtime.py`가 `TokenPrices({}, "no published rate configured")`를
합성해서 단가표가 비어 있다.

⇒ **①만 데모의 얼굴이다.** 헤드라인(`executed · improved · rolled_back`)도, 대본도,
DEVPOST도 전부 ①과 ②만 말한다. ③은 코드와 게이트에만 있고 **화면에 없다.**

### ⭐ 그래서 *"이거 Flagger 아니야?"*의 진짜 답

①+② 만 보이면 그 반론은 **정당하다.** 카나리 배포에서 지표 재고 자동 롤백하는 것은
Flagger·Argo Rollouts·Kayenta가 이미 성숙하게 한다.

**Flagger가 말하지 않는 것은 ③이다** — 그 조치가 **얼마를 썼는지**, 그리고 그 수가
**계산값인지 청구서인지**. 이 저장소는 그 둘을 절대 안 섞는다(REQ-505 · `assumed`는
`measured`가 덮지 않는다).

⚠️ **다만 지금은 그 답을 할 수 없다** — 위에서 본 대로 실물 값이 0이기 때문이다.
③을 화면에 올리는 것과 조치 종류를 늘리는 것은 **다른 일**이고, 전자가 이 반론에 답한다.

⚠️ 트랙(§6)이 우리의 차별점으로 지목하는 것도 ③이다. **문서 셋(§0·§4·§6)이 ③을 가리키는
동안 데모는 ①만 보여 주고 있었다** — 이 어긋남을 여기 적어 둔다.

## 1. 일정

| | |
|---|---|
| Submission Period | **2026-08-03 09:00 PT ~ 2026-08-31 17:00 PT** |
| **한국 제출 마감** | **2026-09-01 09:00 KST** |
| Google Cloud 크레딧 ($150) | 신청 마감 08-28 12:00 PT — ⛔ **별도 발급이 아니다**(08-23 콘솔 확인) |
| 총 상금 | $180,000 |

⛔ **크레딧에 대해 08-23에 확인한 것** — 콘솔의 「발급된 크레딧」에 **해커톤 전용 크레딧은 없다.**
대회가 말한 $150은 **가입하면 주는 기본 Free Trial**이고, 이 계정에는 그것이 이미 있다
(원금 ₩444,063 ≈ $300 · 잔액 ₩332,713). ⚠️ 한때 *"신청했는데 안 왔다"*로 읽었지만 오독이었다.
⛔ **그 크레딧이 2026-09-06에 만료된다** — 제출(09-01)·teardown(09-02) 뒤 여유가 **4일뿐**이다.
그리고 GenAI App Builder 크레딧(₩1,495,986)은 *"특정 방식의 사용"*으로 범위가 제한돼 있어
**Cloud Run 요금엔 안 붙을 수 있다** — 큰 숫자에 안심하지 말 것.

✅ **08-24 중단 기준은 통과했다**(08-23 Cloud Run 배포 · `docs/evidence/deploy-2026-08-23.log`).

⚠️ **자체 중단 기준: 08-24까지 Cloud Run에서 도는 것이 없으면 접는다.**
근거는 남은 일정 산수다 — 마지막 주에 화해·리포트·**4분 영어 영상**·README·다이어그램이
남아야 하고, "배포가 된다"는 그때 이미 참이어야 한다. 포기 비용은 0이다(제출 안 하면 그만).

## 2. 필수 기술 (원문)

- **Gemini 3.5 이상** — Gemini API 또는 Vertex AI
- **Google Agent Framework 1개 이상** — Google ADK / GenAI SDK / Antigravity SDK / GenKit
- **Google Cloud 인프라 1개 이상** — Cloud Run / Cloud SQL / Firestore / GKE / Pub/Sub 등

→ 우리의 대응: `specs/warranty/design/04-agent-runtime.md` §1

## 3. 제출물

- 프로젝트 설명 및 기술 스택
- **코드 저장소 URL** (GitHub/GitLab/Bitbucket · **private 허용**)
- **아키텍처 다이어그램**
- **≤4분 영어 데모 영상** — **Google Cloud 배포의 시각 증거 포함**
- 재현 가능한 실행/배포 절차
- Hosted Project URL (있으면 — 권장 사항)

⚠️ **라이선스 요건 없음** (AWS 쪽 대회와 다른 점).

## 4. 심사 기준

| 항목 | 비중 | 우리의 획득 경로 |
|---|---|---|
| **Innovation & Operational Utility** | **40%** | `executed`≠`improved`를 **따로** 기록(REQ-502) · **검증 가능성이 판정 축**(REQ-402) · 되읽어 **증명하는** 롤백(REQ-303·304) · 액션 단위 귀속과 추정≠실측(REQ-503·504·505) |
| Architectural Discipline & Tech Stack | 30% | ADK + Gemini 3.7 Flash + Cloud Run + Firestore + Monitoring, 포트/어댑터, 상태 주장을 게이트가 집행 |
| Demo & Production Readiness | 30% | 결정론적 `make demo` · **거부와 한계가 화면에 보인다** · 실물 증거 로그 |

⚠️ **어디에도 "규모"가 없다.** 크게 만드는 것은 점수가 아니다.

⛔ **이 표의 첫 칸이 틀려 있었다**(2026-08-29 발견). 40% 항목의 획득 경로로 *"게이트 자신의
예측 오차 측정(REQ-307)"*을 적고 있었는데 **REQ-307은 존재하지 않는다** — REQ-3xx는 305까지다.
가장 비중이 큰 항목의 계획이 **없는 요구사항을 가리키고 있었다.** 실재하는 요구사항으로
바꿨다. ⇒ 항목별 정직한 강약 판정은 [`submission/DEVPOST.md`](../submission/DEVPOST.md) §4.

## 5. 규칙 제약 (원문)

> *"Projects must be newly created during the Submission Period."*
> *"Participants may use standard development tools, including frameworks, libraries,
> starter templates, and AI coding assistants, but must disclose any other pre-existing
> code or work incorporated into the Project."*

→ 우리의 대응과 근거: `docs/REFERENCE_FROM_PARENT.md` §0 · REQ-802

## 6. 트랙 — Fortified Enterprise Fleet

트랙이 제시하는 요소: Agent Registry · Agent Runtime + Memory Bank · Agent Identity +
Gateway · Model Armor · Agent Observability.

**우리가 대응하는 것**: Registry = 운영 계약(REQ-1xx) · Runtime = ADK·Gemini·Cloud
Run(**REQ-6xx**) · **Observability를 두 축으로 확장** — 회복 여부(REQ-2xx·3xx)와
**비용**(**REQ-503·504·505**). 대부분의 agent observability가 토큰·지연·오류만 보고
**에이전트가 만든 클라우드 지출**은 안 본다는 것이 우리가 내세우는 차별점이다.

⛔ **이 칸의 요구사항 번호 둘이 틀려 있었다**(2026-08-29 발견 · §4의 REQ-307과 같은 종류의
버그다). *"Runtime(REQ-5xx)"*라고 적었는데 REQ-5xx는 **책임 원장**이고 런타임은 REQ-6xx다.
*"비용 축으로 확장(REQ-2xx/4xx)"*이라고 적었는데 REQ-2xx는 **검증**, REQ-4xx는 **판정
게이트**이고 **비용은 REQ-5xx**다. ⇒ 차별점이라고 내세운 축의 번호가 **비용이 아닌 곳을
가리키고 있었다.**

⚠️ 그리고 그 차별점은 §0에서 본 대로 **실물에서 아직 0이다.** 여기에 적혀 있다는 것과
데모가 보여 준다는 것은 다른 일이다.

**우리가 대응하지 않는 것**: Identity/Gateway · Model Armor · Memory Bank.
⚠️ **범위를 넓히지 않는다** — 4분 영상에 안 들어간다(`requirements.md` §9).
