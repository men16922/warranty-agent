# 대회 사실관계 — Google All Things Agentic Hackathon

원문 확인: 2026-08-15 (Official Rules) · 이 문서 작성: 2026-08-19
**요구사항의 권위는 `specs/fleet-ledger/requirements.md`다.** 이 문서는 **대회 쪽 사실**만 담는다.

---

## 1. 일정

| | |
|---|---|
| Submission Period | **2026-08-03 09:00 PT ~ 2026-08-31 17:00 PT** |
| **한국 제출 마감** | **2026-09-01 09:00 KST** |
| Google Cloud 크레딧 ($150) | 신청 마감 08-28 12:00 PT — **신청 완료됨(08-19 확인)** |
| 총 상금 | $180,000 |

⚠️ **자체 중단 기준: 08-24까지 Cloud Run에서 도는 것이 없으면 접는다.**
근거는 남은 일정 산수다 — 마지막 주에 화해·리포트·**4분 영어 영상**·README·다이어그램이
남아야 하고, "배포가 된다"는 그때 이미 참이어야 한다. 포기 비용은 0이다(제출 안 하면 그만).

## 2. 필수 기술 (원문)

- **Gemini 3.5 이상** — Gemini API 또는 Vertex AI
- **Google Agent Framework 1개 이상** — Google ADK / GenAI SDK / Antigravity SDK / GenKit
- **Google Cloud 인프라 1개 이상** — Cloud Run / Cloud SQL / Firestore / GKE / Pub/Sub 등

→ 우리의 대응: `specs/fleet-ledger/design/04-agent-runtime.md` §1

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
| **Innovation & Operational Utility** | **40%** | 액션 단위 지출 귀속 + **게이트 자신의 예측 오차 측정**(REQ-307) |
| Architectural Discipline & Tech Stack | 30% | ADK + Gemini 3.5 + Cloud Run + Firestore + BigQuery, 포트/어댑터, 불변식 7종 |
| Demo & Production Readiness | 30% | 결정론적 `make demo` · **거부와 오차가 화면에 보인다** · 한계를 말한다 |

⚠️ **어디에도 "규모"가 없다.** 크게 만드는 것은 점수가 아니다.

## 5. 규칙 제약 (원문)

> *"Projects must be newly created during the Submission Period."*
> *"Participants may use standard development tools, including frameworks, libraries,
> starter templates, and AI coding assistants, but must disclose any other pre-existing
> code or work incorporated into the Project."*

→ 우리의 대응과 근거: `docs/REFERENCE_FROM_PARENT.md` §0 · REQ-802

## 6. 트랙 — Fortified Enterprise Fleet

트랙이 제시하는 요소: Agent Registry · Agent Runtime + Memory Bank · Agent Identity +
Gateway · Model Armor · Agent Observability.

**우리가 대응하는 것**: Registry(REQ-1xx) · Runtime(REQ-5xx) · **Observability를 비용 축으로
확장**(REQ-2xx/4xx) — 대부분의 agent observability가 토큰·지연·오류만 보고 **에이전트가 만든
클라우드 지출**은 안 본다는 것이 우리의 차별점이다.

**우리가 대응하지 않는 것**: Identity/Gateway · Model Armor · Memory Bank.
⚠️ **범위를 넓히지 않는다** — 4분 영상에 안 들어간다(`requirements.md` §9).
