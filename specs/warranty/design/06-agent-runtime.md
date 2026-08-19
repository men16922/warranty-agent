# L4 — 에이전트 런타임 (ADK · Gemini · Cloud Run)

`Satisfies: REQ-601, REQ-602, REQ-603, REQ-604`

---

## 1. 대회 필수 요건 대응

| 요건 | 충족 |
|---|---|
| Gemini 3.5 이상 (Gemini API 또는 Vertex AI) | **Gemini 3.5 Flash · Vertex AI** |
| Google Agent Framework 1개 이상 | **ADK** |
| Google Cloud 인프라 1개 이상 | **Cloud Run** (+ Firestore · Cloud Monitoring · BigQuery) |

## 2. ⚠️ 가장 중요한 경고

**ADK의 실제 API를 아직 확인하지 않았다.** 이 절의 구성은 *의도*이고, T2에서 실물로
검증되기 전까지는 **주장이 아니다.**

스텁 위에서 통과하는 테스트는 *"우리 코드가 이 인터페이스를 이렇게 부른다"*를 말할 뿐
*"그 인터페이스가 존재한다"*를 말하지 않는다.

⇒ **REQ-601·602의 수용 기준은 실물 호출과 실물 배포다.** 그리고 **T2가 08-24 중단 기준의
판정 대상이다.**

## 3. 도구 (의도)

```
   Agent "warranty"
     model: gemini-3.5-flash (Vertex AI)
     tools:
       ├─ provision(spec)          Day-1 — 리소스 생성 + ★ 계약 방출
       ├─ inspect(resource)        계약·최근 신호 조회               (부수효과 없음)
       ├─ remediate(resource, action)  ★ 게이트 → 조치 → 검증 → 롤백
       └─ report(date)             회복률 리포트                     (부수효과 없음)
```

**도구는 4개로 고정한다.** 늘리면 4분 안에 설명이 안 된다.

## 4. ★ 모델의 판단이 하중을 받는 자리 (REQ-204)

`remediate` 안에서, 재측정이 계약의 `tolerance` 안쪽에 떨어졌을 때만 모델이 불린다.

```
   judge_ambiguous(baseline, after, criterion) -> (verdict, rationale)
```

- **명확한 경우는 모델을 안 부른다** — 부르면 판정이 비결정적이 되고 REQ-802가 깨진다.
- **근거(rationale)는 원장에 문장으로 남고 응답에 나온다** (REQ-604).

⚠️ 이 자리가 없으면 이 시스템에서 LLM은 **자연어를 도구 호출로 바꾸는 파서**일 뿐이다.

## 5. 토큰 계량 (REQ-603)

모든 모델 호출은 `ModelPort`를 통과하고, 그 포트가 **호출 1건 = 원장 1행**을 보장한다.
호출부마다 기록을 시키면 언젠가 한 곳이 빠지고, 그 빠짐은 조용하다.

## 6. Cloud Run 구성

| 설정 | 값 | 이유 |
|---|---|---|
| `min-instances` | **0** | 유휴 과금 0 (REQ-805) |
| `max-instances` | 2 | 폭주 방지 |
| `cpu`/`memory` | 1 / 512Mi | |
| 인증 | 미인증 (데모) | ⚠️ **게이트가 유일한 지출 방어선이다** → 예산 한도를 낮게 |

**콜드 스타트**: 촬영 직전 워밍 요청 1회. ⚠️ **`min-instances`를 바꿔 찍고 되돌리지 않는다** —
영상 속 시스템이 제출물과 달라진다.
