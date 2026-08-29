# 대회 사실관계 — Google All Things Agentic Hackathon

원문 확인: 2026-08-15 (Official Rules) · 이 문서 작성: 2026-08-19
**요구사항의 권위는 `specs/warranty/requirements.md`다.** 이 문서는 **대회 쪽 사실**과
그 사실에 대한 **우리의 대응 매핑**만 담는다. 논지·서사의 권위는 `docs/OVERVIEW.md`다.

---

## 0. 이 프로젝트가 이 대회에서 하는 것

> ⚠️ 여기는 **매핑**이다. 논지 원문은 [`requirements.md` §0](../specs/warranty/requirements.md),
> 그림과 서사는 [`OVERVIEW.md`](OVERVIEW.md)가 소유한다. 여기서 다시 정의하지 않는다.

### 목적 — 한 문장

> **에이전트 함대를 프로덕션에 붙였을 때, 밤새 걔네가 뭘 했는지 아침에 어떻게 아는가.**

⚠️ **2026-08-30에 논지를 바꿨다.** 이전 문장은 *"클라우드 중립성을 포기하면 에이전트가
무엇을 할 수 있게 되는가"*였다. 정확했지만 **멀티클라우드 추상화를 이미 고민해 본 사람만
공감했고**, 그 프레임은 이 프로젝트를 **카나리 배포 도구와 같은 링**에 올려놨다
(아래 Flagger 문단이 그 반론을 이미 적어 두고 있었다). **코드는 한 줄도 안 바꿨다 —
같은 코드가 답하는 질문을 바꿨다.**

로그는 전부 `completed`라고 말한다. 그런데 서비스는 어젯밤과 똑같이 느리다.
**"실행됨"과 "나아짐"은 다른 칸**인데, 대부분의 도구에는 두 번째 칸이 없다.

| # | 원장이 세는 것 | 요구사항 | 심사 항목 | 트랙 요소 |
|---|---|---|---|---|
| ① | **나아졌는가** — 같은 신호로 다시 잰다 | REQ-2xx | Innovation 40% | Agent Observability |
| ② | **되돌렸는가** — 주장이 아니라 배분을 되읽어 증명한다 | REQ-3xx | Innovation 40% | Agent Observability |
| ③ | **얼마 썼는가** — 그 수를 **청구서에서 되찾을 수 있는가** | REQ-503·504·505 | Innovation 40% | Agent Observability |
| ④ | **아예 안 했는가** — 못 재는 일은 실행하지 않는다 | REQ-4xx | Innovation 40% | Agent Observability |

⭐ **④가 이 프레임에서 새로 무기가 됐다.** 이전 논지에서는 곁가지였는데,
*"에이전트를 믿어도 되나"*를 묻는 순간 **자기 한계를 아는 에이전트**가 핵심이 된다.

그리고 넷을 잇는 것이 **운영 계약**(REQ-1xx)이다 — 인프라를 만든 에이전트가 그것을 어떻게
검증·롤백하는지도 함께 적어 둔다. 판정 게이트가 그 계약을 읽어 **검증할 수 없는 조치를
자동 실행에서 뺀다.** 그것이 이 프로젝트의 정책 한 줄이다.

### ⛔ 2026-08-30 — 이 시스템이 자기 논지에 네 번 걸렸다

*"실행했다 ≠ 나아졌다"*를 주장하는 시스템이 **정작 자기 개선을 못 읽고 있었다.**

| # | 무엇 | 왜 안 보였나 |
|---|---|---|
| ① | 재측정 창이 조치 **이전**을 물었다 (대기 45s < 창 120s) | 판정이 `not_recovered`로 그럴듯했다 |
| ② | 회복 기준이 **도달 불가**였다 (60% 요구 / 31% 최대) | 성공이 불가능한 판정기의 실패 보고 |
| ③ | 계약이 **옛 정책**을 들고 있었다 | 코드를 고쳐도 안 바뀐다 (설계상 맞다) |
| ④ | 기다림을 늘리자 **답이 죽었다** (타임아웃 300s) | 조치는 나갔고 원장은 옳았다 — **답만** 사라졌다 |

실물 증거: `990.04 → 674.17ms`(**32% 개선**)가 `not_recovered`를 받았다.
셋은 가드+변이가 됐고(M-281·M-282·M-283·M-284·M-285), 하나는 기록에 있다
(오프라인 게이트는 Firestore를 안 연다 — G5).
⚠️ **로그로 못 찾았다.** 어긋나면 안 되는 두 숫자를 노려보다 찾았다.
증거: `docs/evidence/verify-window-2026-08-30.log`.

### ⭐ *"이거 Flagger 아니야?"*의 답 — 링이 다르다

카나리 배포에서 지표 재고 자동 롤백하는 것은 Flagger·Argo Rollouts가 이미 성숙하게 한다.
**그런데 Flagger는 에이전트가 아니다.** 배포 파이프라인이고, 사람이 분석 규칙을 미리 짠다.

여기서 다른 것은 두 가지다:
- **계약을 에이전트가 쓴다.** 리소스를 만든 그 에이전트가 *"이게 아플 때 어떻게 아는지"*를
  같이 기록한다. 3개월 뒤 만든 사람이 떠나도 다음 에이전트가 그 계약을 읽는다.
- **상품이 조치가 아니라 회계다.** 조치가 몇 종류든 성립하고, **조치가 늘어날수록 더 필요해진다.**
  그게 트랙 이름(*Fortified Enterprise **Fleet***)이 가리키는 것이다.

⚠️ 여전히 정직하게 남는 약점: **조치 종류가 둘뿐이다**(`traffic:`·`concurrency:`).
   *"똑똑하게 고치는 에이전트"*로는 이 저장소가 안 이긴다. 이기려는 링은 **회계**다.

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
