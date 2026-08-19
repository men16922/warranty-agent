# spec — fleet-ledger

**대회**: Google All Things Agentic Hackathon · **트랙**: Fortified Enterprise Fleet
**제출 마감**: 2026-09-01 09:00 KST · **작성**: 2026-08-19

---

## 이 폴더가 무엇인가

**이 spec이 단일 권위(single source of truth)다.** 코드가 spec과 다르면 **코드가 틀린 것**이고,
설계를 바꾸려면 **spec을 먼저 고친다.** 이 순서를 규율이 아니라 **게이트가 집행한다**(G6, `design/07-verification.md`).

이 규약이 필요한 이유는 이 저장소가 아니라 **레퍼런스 저장소에서 배운 것**이다:
권위 문서가 틀렸을 때 진입점 세 곳이 그 숫자를 복제해 **승인까지 갔고, 100배 틀렸다**
(`docs/REFERENCE_FROM_PARENT.md` #1). 권위를 한 곳에 두고 나머지는 **가리키기만 한다.**

## 읽는 순서

| # | 문서 | 레벨 | 무엇을 답하나 |
|---|---|---|---|
| 1 | `requirements.md` | L1 | **무엇을 만족해야 하는가** — REQ-### + 수용 기준. **가장 높은 권위** |
| 2 | `design.md` | L2 | **왜 이 구조인가** — 아키텍처 개요 + 설계 문서 지도 |
| 3 | `design/01-domain-model.md` | L3 | 도메인 모델 · 불변식 |
| 4 | `design/02-attribution.md` | L4 | ★ **귀속 메커니즘** — 이 프로젝트의 핵심 |
| 5 | `design/03-budget-gate.md` | L4 | 예산 게이트 (거부의 집행) |
| 6 | `design/04-agent-runtime.md` | L4 | ADK · Gemini · Cloud Run |
| 7 | `design/05-reconciliation.md` | L4 | BQ 결제 내보내기 화해 |
| 8 | `design/06-interfaces.md` | L5 | 포트/어댑터 · HTTP 계약 |
| 9 | `design/07-verification.md` | L6 | 테스트 전략 · 게이트 · 변이 검증 |
| 10 | `design/08-deployment.md` | L7 | 인프라 · IAM · teardown |
| 11 | `design/09-demo.md` | L8 | 실증 최적화 · 4분 영상 |
| 12 | `tasks.md` | — | 실행 계획. 각 태스크가 REQ와 설계 절을 가리킨다 |

**spec 밖의 문서**(`docs/`)는 권위가 아니다:
`docs/HACKATHON.md`(대회 사실관계) · `docs/DECISIONS.md`(ADR) ·
`docs/REFERENCE_FROM_PARENT.md`(레퍼런스 추출물) · `docs/COST_GUARDRAILS.md`(운영 규약).

## 추적성 규약 (SDD의 척추)

```
  requirements.md          design/*.md              tasks.md              tests/
  ─────────────────        ───────────              ────────              ──────
  REQ-204          ←Satisfies─  §불변식 I-3   ←Design─  T4-2   ←Verifies─  test_req_204_*
```

1. **모든 요구사항은 ID를 갖는다** — `REQ-###`. ID는 재사용하지 않는다(폐기해도 번호는 남긴다).
2. **모든 설계 절은 자신이 만족하는 REQ를 선언한다** — 절 머리에 `Satisfies: REQ-###`.
3. **모든 태스크는 REQ와 설계 절을 가리킨다** — `Implements: REQ-### · Design: <파일>§<절>`.
4. **모든 REQ는 최소 1개의 테스트가 이름으로 가리킨다** — `test_req_204_...`.
5. **④를 가드가 집행한다(G6)** — `requirements.md`를 파싱해 모든 REQ ID가 테스트에서
   참조되는지 확인한다. 참조 없는 REQ가 있으면 **게이트가 red**다.

⚠️ **G6가 없으면 이 문서 전체가 장식이다.** spec-driven과 spec-decorated를 가르는 건
문서의 존재가 아니라 **spec을 안 지키면 빌드가 깨지는가**이다.

## 상태 표기

요구사항 각 항목은 상태를 갖는다: `TODO` · `DESIGNED` · `IMPLEMENTED` · `VERIFIED` · `DROPPED`.
**`VERIFIED`는 테스트가 있고 그 테스트를 지웠을 때 red가 확인된 것만** 쓴다
(`docs/REFERENCE_FROM_PARENT.md` #9).
